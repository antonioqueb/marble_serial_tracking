from odoo import models, fields
import logging
_logger = logging.getLogger(__name__)
class StockMove(models.Model):
    _inherit = 'stock.move'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados')
    lot_general = fields.Char('Lote General')

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
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
