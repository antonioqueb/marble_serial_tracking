# models/stock_quant.py
from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    marble_height    = fields.Float(related='lot_id.marble_height', store=True)
    marble_width     = fields.Float(related='lot_id.marble_width',  store=True)
    marble_sqm       = fields.Float(related='lot_id.marble_sqm',    store=True)
    lot_general      = fields.Char (related='lot_id.lot_general',   store=True)
    pedimento_number = fields.Char (related='lot_id.pedimento_number', store=True)
