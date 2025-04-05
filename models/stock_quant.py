from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    marble_height = fields.Float('Altura (m)', related='lot_id.move_line_ids.marble_height', store=True)
    marble_width = fields.Float('Ancho (m)', related='lot_id.move_line_ids.marble_width', store=True)
    marble_sqm = fields.Float('Metros Cuadrados', related='lot_id.move_line_ids.marble_sqm', store=True)
    lot_general = fields.Char('Lote General', related='lot_id.move_line_ids.lot_general', store=True)
