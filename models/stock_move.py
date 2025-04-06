from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    # Campo Many2one para forzar el lote escogido en la venta
    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")

    # Campos de mármol
    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados')
    lot_general = fields.Char('Lote General')

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        """
        Mantiene la lógica original de crear la move line 
        con los campos de mármol.
        """
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)
        vals.update({
            'marble_height': self.marble_height,
            'marble_width': self.marble_width,
            'marble_sqm': self.marble_sqm,
            'lot_general': self.lot_general,
        })
        _logger.info(f"Move line creado con valores: {vals}")
        return vals

    def _create_move_lines(self):
        """
        Tras crear las líneas, completa los valores de mármol
        si vienen vacíos en el move line.
        """
        res = super()._create_move_lines()
        for move in self:
            for line in move.move_line_ids:
                if not line.marble_height:
                    line.marble_height = move.marble_height
                if not line.marble_width:
                    line.marble_width = move.marble_width
                if not line.marble_sqm:
                    line.marble_sqm = move.marble_sqm
                if not line.lot_general:
                    line.lot_general = move.lot_general
        return res

    def _action_assign(self):
        """
        Sobrescribimos la asignación de stock para forzar que,
        si hay un lote específico 'so_lot_id' proveniente de la venta,
        se reserve en ese lote y no según la política FIFO.
        """
        # Primero dejamos que Odoo haga la reserva estándar
        super()._action_assign()

        # Luego forzamos la reserva en el lote si 'so_lot_id' está presente
        for move in self.filtered(lambda m: m.state in ('confirmed', 'partially_available', 'waiting')):
            if move.product_id.tracking != 'none' and move.so_lot_id:
                lot = move.so_lot_id
                _logger.info(f"Forzando reserva en lote {lot.name} para Move {move.id} ({move.product_id.display_name})")

                already_reserved = sum(move.move_line_ids.mapped('product_uom_qty'))
                missing_to_reserve = move.product_uom_qty - already_reserved
                if missing_to_reserve > 0:
                    # Verificamos stock disponible en ese lote
                    available_qty = self.env['stock.quant']._get_available_quantity(
                        move.product_id,
                        move.location_id,
                        lot_id=lot,
                        package_id=False,
                        owner_id=False,
                        strict=True
                    )
                    if available_qty <= 0:
                        _logger.warning(f"No hay stock disponible en el lote {lot.name}.")
                        continue

                    qty_to_reserve = min(missing_to_reserve, available_qty)
                    existing_line = move.move_line_ids.filtered(lambda ml: ml.lot_id == lot)
                    if existing_line:
                        existing_line.product_uom_qty += qty_to_reserve
                    else:
                        self.env['stock.move.line'].create({
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'lot_id': lot.id,
                            # Normalmente en salidas, 'product_uom_qty' define la reserva;
                            # 'qty_done' se llena al validar la transferencia.
                            'product_uom_qty': qty_to_reserve,
                        })
        return True
