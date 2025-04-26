# models/sale_order_line.py
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie',
        domain="[('product_id', '=', product_id)]"
    )

    # ─── Datos que bajan al flujo logístico ───
    marble_height     = fields.Float(related='lot_id.marble_height',     store=True, readonly=True)
    marble_width      = fields.Float(related='lot_id.marble_width',      store=True, readonly=True)
    marble_sqm        = fields.Float(related='lot_id.marble_sqm',        store=True, readonly=True)
    lot_general       = fields.Char (related='lot_id.lot_general',       store=True, readonly=True)

    # ─── Propagación al procurement / stock.move ───
    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id)
        vals.update({
            'lot_id':           self.lot_id.id,
            'marble_height':    self.marble_height,
            'marble_width':     self.marble_width,
            'marble_sqm':       self.marble_sqm,
            'lot_general':      self.lot_general
        })
        return vals
