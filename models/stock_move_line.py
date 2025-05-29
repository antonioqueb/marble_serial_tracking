# models/stock_move_line.py
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # ─────────── Campos extendidos ───────────
    marble_height = fields.Float('Altura (m)')
    marble_width  = fields.Float('Ancho (m)')
    marble_sqm    = fields.Float('Metros Cuadrados')
    lot_general   = fields.Char('Lote General')
    bundle_code   = fields.Char('Bundle Code')
    marble_thickness = fields.Float('Grosor (cm)')


    # ─────────── Creación automática de lote ───────────
    @api.model_create_multi
    def create(self, vals_list):
        """
        Para recepciones (*incoming*):
        • Si viene `lot_general` y NO `lot_id`, se crea SIEMPRE un
          nuevo `stock.lot` secuencial (no se reutiliza ninguno),
          logrando nombres UYI-001, UYI-002, UYI-003…
        """
        lots_env = self.env['stock.lot']
        seq_env  = self.env['ir.sequence'].sudo()

        # 🔸 PRE-LOG
        for vals in vals_list:
            _logger.debug("[SML-CREATE|PRE] vals=%s", vals)

        # 1) Generar / asignar lote ANTES de super()
        for vals in vals_list:
            # ► Sólo si aún no hay lote y viene `lot_general`
            if vals.get('lot_id') or not vals.get('lot_general'):
                continue

            bundle_code_val = vals.get('bundle_code')

            # ► Verificar que la línea pertenezca a un picking de entrada
            picking_code = vals.get('picking_code')  # cuando viene del escáner
            if not picking_code:
                move = self.env['stock.move'].browse(vals.get('move_id'))
                picking_code = move.picking_type_id.code

            if picking_code != 'incoming':
                _logger.debug(
                    "[SML-CREATE] No es 'incoming' (code=%s) → sin lote auto",
                    picking_code
                )
                continue

            lot_general = vals['lot_general']
            product_id  = vals.get('product_id')

            # 1.1) Asegurar secuencia específica por `lot_general`
            seq_code = f"marble.serial.{lot_general}"
            sequence = seq_env.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = seq_env.create({
                    'name':   _('Secuencia Mármol %s') % lot_general,
                    'code':   seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })
                _logger.debug("[SEQ] Creada nueva secuencia %s", seq_code)

            # 1.2) Generar SIEMPRE un lote nuevo (no se reutiliza)
            lot_name = sequence.next_by_id()
            vals['lot_id'] = lots_env.create({
                'name':          lot_name,
                'product_id':    product_id,
                'company_id':    vals.get('company_id'),
                'marble_height': vals.get('marble_height'),
                'marble_width':  vals.get('marble_width'),
                'marble_sqm':    vals.get('marble_sqm'),
                'lot_general':   lot_general,
                'bundle_code':   bundle_code_val,
                'marble_thickness': vals.get('marble_thickness', 0.0),
            }).id
           

        # 2) Crear las líneas normalmente
        move_lines = super().create(vals_list)

       
        return move_lines

    def write(self, vals):
        """
        Extiende el método write para generar lotes secuenciales automáticos
        al recibir un valor en lot_general durante la edición manual.
        """
        lots_env = self.env['stock.lot']
        seq_env = self.env['ir.sequence'].sudo()

        for line in self:
            if 'lot_general' in vals and vals['lot_general'] and not line.lot_id:
                # Solo aplicarlo para líneas en recepciones entrantes
                picking_code = line.picking_id.picking_type_id.code
                if picking_code != 'incoming':
                    _logger.debug(
                        "[SML-WRITE] No es 'incoming' (code=%s) → sin lote auto",
                        picking_code
                    )
                    continue

                lot_general = vals['lot_general']
                product_id = vals.get('product_id', line.product_id.id)

                # Crear o buscar secuencia específica por `lot_general`
                seq_code = f"marble.serial.{lot_general}"
                sequence = seq_env.search([('code', '=', seq_code)], limit=1)
                if not sequence:
                    sequence = seq_env.create({
                        'name': _('Secuencia Mármol %s') % lot_general,
                        'code': seq_code,
                        'padding': 3,
                        'prefix': f"{lot_general}-",
                    })
                    _logger.debug("[SEQ-WRITE] Creada nueva secuencia %s", seq_code)

                # Generar SIEMPRE un lote nuevo (no reutilizar)
                lot_name = sequence.next_by_id()
                lot_vals = {
                    'name': lot_name,
                    'product_id': product_id,
                    'company_id': line.company_id.id,
                    'marble_height': vals.get('marble_height', line.marble_height),
                    'marble_width': vals.get('marble_width', line.marble_width),
                    'marble_sqm': vals.get('marble_sqm', line.marble_sqm),
                    'lot_general': lot_general,
                    'bundle_code': vals.get('bundle_code', line.bundle_code),
                    'marble_thickness': vals.get('marble_thickness', line.marble_thickness),
                }
                new_lot = lots_env.create(lot_vals)
                vals['lot_id'] = new_lot.id

                _logger.debug(
                    "[SML-WRITE] Creado nuevo lote secuencial: %s para línea ID: %s",
                    lot_name, line.id
                )

        return super().write(vals)
