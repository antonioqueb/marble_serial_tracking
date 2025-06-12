# models/stock_picking.py

from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _sync_moves_with_lots(self):
        """
        Función clave para asegurar la coherencia de datos.
        Itera sobre todos los movimientos y fuerza que sus datos de mármol
        reflejen los del lote que tienen asignado.
        Esto previene la propagación de datos incorrectos (ej. dimensiones cero).
        """
        _logger.info(f"[{self.name}] Sincronización forzada: Asegurando que los datos del move coincidan con el lote asignado.")
        for move in self.move_ids_without_package:
            # Condición 1: El movimiento tiene un lote asignado.
            # Condición 2: Los m² del movimiento no coinciden con los m² del lote O el pedimento no coincide (indicador de desincronización).
            if move.lot_id and (
                move.marble_sqm != move.lot_id.marble_sqm or
                (hasattr(move, 'pedimento_number') and hasattr(move.lot_id, 'pedimento_number') and move.pedimento_number != move.lot_id.pedimento_number)
            ):
                _logger.warning(f"[{self.name}] Detectada inconsistencia en Move {move.id}. Lote {move.lot_id.name} asignado pero datos no coinciden.")
                _logger.warning(f"  - Move SQM: {move.marble_sqm}, Lote SQM: {move.lot_id.marble_sqm}. Forzando actualización del MOVE.")

                # Se obtienen los datos del quant para el número de pedimento
                quant = self.env['stock.quant'].search([
                    ('lot_id', '=', move.lot_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                ], limit=1, order='in_date DESC')

                # Actualizar el movimiento para que refleje los datos correctos de su lote.
                move.with_context(skip_sync=True).write({
                    'marble_height':    move.lot_id.marble_height,
                    'marble_width':     move.lot_id.marble_width,
                    'marble_sqm':       move.lot_id.marble_sqm,
                    'lot_general':      move.lot_id.lot_general,
                    'marble_thickness': move.lot_id.marble_thickness,
                    'pedimento_number': quant.pedimento_number or '',
                })

    def write(self, vals):
        """
        Sobrescribimos write para ejecutar la sincronización al guardar.
        Esto mejora la experiencia de usuario, evitando "reseteos" visuales.
        """
        # Primero, ejecutar el write original
        res = super().write(vals)
        # Después de cualquier escritura, ejecutar la sincronización.
        # Esto es especialmente útil después de añadir nuevas líneas.
        if self.state not in ('done', 'cancel'):
            for picking in self:
                picking._sync_moves_with_lots()
        return res

    def button_validate(self):
        _logger.info(f"[PICKING-VALIDATE] === INICIO validación de picking {self.name} ===")
        
        # --- PASO 1: Sincronización Forzada y Preventiva ---
        self._sync_moves_with_lots()
        
        # --- PASO 2: Sincronización opcional desde la Venta (si el move está vacío) ---
        if self.picking_type_id.code == 'outgoing':
            _logger.info("[PICKING-VALIDATE] Es una salida. Verificando sincronización con líneas de venta.")
            for move in self.move_ids_without_package:
                if move.sale_line_id and not move.lot_id and not move.marble_sqm > 0:
                    sale = move.sale_line_id
                    _logger.info(f"[PICKING-VALIDATE] Move {move.id} sin datos, intentando sincronizar desde Venta {sale.id}")
                    if sale.marble_sqm > 0 or sale.lot_id:
                        move.write({
                            'marble_height':    sale.marble_height,
                            'marble_width':     sale.marble_width,
                            'marble_sqm':       sale.marble_sqm,
                            'lot_general':      sale.lot_general,
                            'marble_thickness': sale.marble_thickness,
                            'pedimento_number': sale.pedimento_number,
                            'lot_id':           sale.lot_id.id,
                        })
                else:
                    _logger.info(f"[PICKING-VALIDATE] Move {move.id} ya tiene datos o no tiene línea de venta. No se sincroniza desde venta.")
                    
        # --- PASO 3: Propagación Final a las Líneas de Operación ---
        _logger.info("[PICKING-VALIDATE] Propagando datos de moves (ya corregidos) a move_lines (pre-validación).")
        for move in self.move_ids_without_package:
            if move.lot_id or move.marble_sqm > 0:
                _logger.info(f"[PICKING-VALIDATE] Move {move.id} tiene datos para propagar.")
                move._propagate_marble_data_to_move_lines()

        _logger.info("[PICKING-VALIDATE] Llamando a super().button_validate()")
        result = super().button_validate()
        
        _logger.info(f"[PICKING-VALIDATE] === FIN validación de picking {self.name} ===")
        return result

    def _action_done(self):
        _logger.info(f"[PICKING-DONE] === INICIO _action_done para picking {self.name} ===")
        
        # Como red de seguridad final, volvemos a sincronizar y corregir.
        _logger.info("[PICKING-DONE] Verificación y corrección final de datos en move_lines antes de super().")
        for line in self.move_line_ids.filtered(lambda l: l.lot_id and l.quantity > 0):
            lot = line.lot_id
            
            expected_data = {
                'marble_height': lot.marble_height,
                'marble_width': lot.marble_width,
                'marble_sqm': lot.marble_sqm,
                'lot_general': lot.lot_general,
                'marble_thickness': lot.marble_thickness,
            }
            
            # Buscamos el pedimento del quant correspondiente
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id), ('quantity', '>', 0), ('location_id.usage', '=', 'internal'),
            ], limit=1, order='in_date DESC')
            if quant:
                expected_data['pedimento_number'] = quant.pedimento_number or ''

            # Creamos un diccionario con los datos a verificar/actualizar
            data_to_write = {}
            for field, value in expected_data.items():
                if getattr(line, field) != value:
                    data_to_write[field] = value

            if data_to_write:
                _logger.warning(f"[PICKING-DONE] ¡CORRIGIENDO! Inconsistencia encontrada en la línea {line.id} durante _action_done.")
                _logger.warning(f"  - Datos a actualizar: {data_to_write}")
                line.write(data_to_write)
        
        result = super()._action_done()
        
        _logger.info(f"[PICKING-DONE] === FIN _action_done para picking {self.name} ===")
        return result