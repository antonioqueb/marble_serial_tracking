# models/purchase_order_line.py
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    marble_height = fields.Float('Altura (m)', store=True)
    marble_width = fields.Float('Ancho (m)', store=True)
    marble_sqm = fields.Float('Metros Cuadrados', compute='_compute_marble_sqm', store=True)
    lot_general = fields.Char('Lote General', store=True)

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            altura = line.marble_height or 0.0
            ancho = line.marble_width or 0.0
            line.marble_sqm = altura * ancho
            _logger.debug(f"[MARBLE-COMPUTE] PO Line ID {line.id}: altura={altura}, ancho={ancho} → m²={line.marble_sqm}")
