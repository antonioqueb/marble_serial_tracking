# models/stock_lot.py
from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    # …campos ya existentes…
    marble_height = fields.Float('Altura (m)')
    marble_width  = fields.Float('Ancho (m)')
    marble_sqm    = fields.Float('Metros Cuadrados')
    lot_general   = fields.Char('Lote General')

    pedimento_number = fields.Char('Número de Pedimento', size=18, readonly=True)
