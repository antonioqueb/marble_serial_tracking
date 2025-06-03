# models/stock_move_line.py
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            line.marble_sqm = (line.marble_height or 0.0) * (line.marble_width or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        lots_env = self.env['stock.lot']
        seq_env = self.env['ir.sequence'].sudo()

        for vals in vals_list:
            _logger.debug("[SML-CREATE|PRE] vals=%s", vals)

        for vals in vals_list:
            if vals.get('lot_id') or not vals.get('lot_general'):
                continue

            

            picking_code = vals.get('picking_code')
            if not picking_code:
                move = self.env['stock.move'].browse(vals.get('move_id'))
                picking_code = move.picking_type_id.code

            if picking_code != 'incoming':
                continue

            lot_general = vals['lot_general']
            product_id = vals.get('product_id')

            seq_code = f"marble.serial.{lot_general}"
            sequence = seq_env.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = seq_env.create({
                    'name': _('Secuencia Mármol %s') % lot_general,
                    'code': seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })

            lot_name = sequence.next_by_id()
            vals['lot_id'] = lots_env.create({
                'name': lot_name,
                'product_id': product_id,
                'company_id': vals.get('company_id'),
                'marble_height': vals.get('marble_height'),
                'marble_width': vals.get('marble_width'),
                'marble_sqm': (vals.get('marble_height') or 0.0) * (vals.get('marble_width') or 0.0),
                'lot_general': lot_general,
                'marble_thickness': vals.get('marble_thickness', 0.0),
            }).id

        move_lines = super().create(vals_list)
        return move_lines

    def write(self, vals):
        """
        Método write mejorado que maneja correctamente la creación de secuencias
        cuando se actualiza lot_general desde cualquier vista
        """
        # Si no hay lot_general en vals, usar comportamiento normal
        if 'lot_general' not in vals or not vals['lot_general']:
            return super().write(vals)

        lots_env = self.env['stock.lot']
        seq_env = self.env['ir.sequence'].sudo()
        
        # Identificar líneas que necesitan procesamiento
        lines_to_process = self.filtered(lambda line: not line.lot_id)
        
        if not lines_to_process:
            _logger.debug("[SML-WRITE] No hay líneas sin lote para procesar")
            return super().write(vals)

        _logger.info(f"[SML-WRITE] Procesando {len(lines_to_process)} líneas para lot_general: {vals['lot_general']}")
        
        # Procesar cada línea individualmente para evitar conflictos
        for line in lines_to_process:
            # Verificar que es un picking de entrada
            picking_code = line.picking_id.picking_type_id.code if line.picking_id else 'unknown'
            if picking_code != 'incoming':
                _logger.debug(f"[SML-WRITE] Línea {line.id} no es de entrada ({picking_code}), saltando")
                continue

            lot_general = vals['lot_general']
            product_id = vals.get('product_id', line.product_id.id)

            _logger.info(f"[SML-WRITE] Procesando línea {line.id} para lote_general: {lot_general}")

            # Buscar o crear secuencia de forma segura
            seq_code = f"marble.serial.{lot_general}"
            
            # Usar transacción para evitar problemas de concurrencia
            try:
                with self.env.cr.savepoint():
                    sequence = seq_env.search([('code', '=', seq_code)], limit=1)
                    if not sequence:
                        sequence = seq_env.create({
                            'name': _('Secuencia Mármol %s') % lot_general,
                            'code': seq_code,
                            'padding': 3,
                            'prefix': f"{lot_general}-",
                        })
                        _logger.info(f"[SML-WRITE] Secuencia creada: {seq_code}")
            except Exception as e:
                _logger.warning(f"[SML-WRITE] Error en savepoint para secuencia {seq_code}: {e}")
                # Si falla, buscar de nuevo por si otro proceso la creó
                sequence = seq_env.search([('code', '=', seq_code)], limit=1)
                if not sequence:
                    _logger.error(f"[SML-WRITE] No se pudo crear ni encontrar secuencia {seq_code}")
                    continue

            # Generar número de serie único
            try:
                lot_name = sequence.next_by_id()
                _logger.info(f"[SML-WRITE] Número de serie generado: {lot_name}")
            except Exception as e:
                _logger.error(f"[SML-WRITE] Error generando número de serie: {e}")
                continue

            # Preparar valores para el nuevo lote
            lot_vals = {
                'name': lot_name,
                'product_id': product_id,
                'company_id': line.company_id.id,
                'marble_height': vals.get('marble_height', line.marble_height),
                'marble_width': vals.get('marble_width', line.marble_width),
                'marble_sqm': (vals.get('marble_height', line.marble_height) or 0.0) * (vals.get('marble_width', line.marble_width) or 0.0),
                'lot_general': lot_general,
                'marble_thickness': vals.get('marble_thickness', line.marble_thickness),
            }

            # Crear el lote
            try:
                new_lot = lots_env.create(lot_vals)
                _logger.info(f"[SML-WRITE] Lote creado: {new_lot.name} (ID: {new_lot.id})")
                
                # Preparar valores para actualizar la línea
                line_vals = vals.copy()
                line_vals['lot_id'] = new_lot.id
                
                # Actualizar solo esta línea específica
                super(StockMoveLine, line).write(line_vals)
                _logger.info(f"[SML-WRITE] Línea {line.id} actualizada con lote {new_lot.name}")
                
            except Exception as e:
                _logger.error(f"[SML-WRITE] Error creando lote para línea {line.id}: {e}")
                # Si falla la creación del lote, actualizar solo los otros campos
                super(StockMoveLine, line).write(vals)

        # Para las líneas que ya tenían lote, usar comportamiento normal
        lines_with_lot = self.filtered(lambda line: line.lot_id)
        if lines_with_lot:
            super(StockMoveLine, lines_with_lot).write(vals)

        return True

    @api.onchange('lot_general')
    def _onchange_lot_general(self):
        """
        OnChange para preview en la interfaz cuando se cambia lot_general
        """
        if self.lot_general and not self.lot_id:
            # Solo para preview - no crear lotes reales en onchange
            next_number = f"{self.lot_general}-XXX"  # Preview genérico
            
            # Mostrar mensaje informativo (opcional)
            return {
                'warning': {
                    'title': _('Información'),
                    'message': _('Se generará automáticamente un número de serie como: %s al guardar') % next_number
                }
            }