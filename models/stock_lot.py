from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados')
    lot_general = fields.Char('Lote General')
    bundle_code = fields.Char('Bundle Code')
    marble_thickness = fields.Float('Grosor (cm)')
