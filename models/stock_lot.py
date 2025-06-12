from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²')
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    numero_contenedor = fields.Char('Número de Contenedor')
