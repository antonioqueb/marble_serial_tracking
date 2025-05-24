from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    marble_height = fields.Float('Altura (m)', related='lot_id.marble_height', store=True)
    marble_width = fields.Float('Ancho (m)', related='lot_id.marble_width', store=True)
    marble_sqm = fields.Float('Metros Cuadrados', related='lot_id.marble_sqm', store=True)
    lot_general = fields.Char('Lote General', related='lot_id.lot_general', store=True)
    bundle_code = fields.Char('Bundle Code', related='lot_id.bundle_code', store=True)
    marble_thickness = fields.Float('Grosor (cm)', related='lot_id.marble_thickness', store=True)
