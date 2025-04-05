from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados', compute='_compute_marble_sqm', store=True)
    lot_general = fields.Char('Lote General')

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            line.marble_sqm = line.marble_height * line.marble_width


    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        
        # Aquí verificamos exactamente qué valores se tienen en memoria
        _logger.info(f"Propagando desde PO line: ID {self.id}, marble_height={self.marble_height}, marble_width={self.marble_width}, marble_sqm={self.marble_sqm}, lot_general={self.lot_general}")

        vals.update({
            'marble_height': self.marble_height,
            'marble_width': self.marble_width,
            'marble_sqm': self.marble_sqm,
            'lot_general': self.lot_general,
        })

        _logger.info(f"Valores finales enviados a move: {vals}")
        return vals
