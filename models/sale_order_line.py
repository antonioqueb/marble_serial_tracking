from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lot_id = fields.Many2one('stock.lot', string='Número de Serie', domain="[('product_id', '=', product_id)]")
    marble_height = fields.Float('Altura (m)', related='lot_id.marble_height', store=True, readonly=True)
    marble_width = fields.Float('Ancho (m)', related='lot_id.marble_width', store=True, readonly=True)
    marble_sqm = fields.Float('Metros Cuadrados', related='lot_id.marble_sqm', store=True, readonly=True)
    lot_general = fields.Char('Lote General', related='lot_id.lot_general', store=True, readonly=True)

    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id)
        vals.update({
            'marble_height': self.marble_height,
            'marble_width': self.marble_width,
            'marble_sqm': self.marble_sqm,
            'lot_general': self.lot_general,
            'lot_id': self.lot_id.id,
        })
        return vals
