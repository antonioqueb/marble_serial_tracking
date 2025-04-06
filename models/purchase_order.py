from odoo import models
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _prepare_stock_moves(self, picking):
        res = super()._prepare_stock_moves(picking)
        _logger.info("[MARBLE-FIX] Ejecutando _prepare_stock_moves en PurchaseOrder")
        for move in res:
            po_line = move.purchase_line_id
            if po_line:
                move.update({
                    'marble_height': po_line.marble_height or 0.0,
                    'marble_width': po_line.marble_width or 0.0,
                    'marble_sqm': po_line.marble_sqm or 0.0,
                    'lot_general': po_line.lot_general or '',
                })
                _logger.info(f"[MARBLE-FIX] Move ID {move.id} actualizado con valores desde PO Line {po_line.id}: "
                             f"height={po_line.marble_height}, width={po_line.marble_width}, "
                             f"sqm={po_line.marble_sqm}, lote={po_line.lot_general}")
        return res
