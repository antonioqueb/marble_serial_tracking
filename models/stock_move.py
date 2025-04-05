from odoo import models, fields

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
        return vals
