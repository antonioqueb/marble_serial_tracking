from odoo import models
import logging
# FUNCIONAL

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _prepare_stock_moves(self, picking):
        self.ensure_one()
        _logger.info("[MARBLE-FIX] Ejecutando _prepare_stock_moves en PurchaseOrder")
        res = super()._prepare_stock_moves(picking)

        for move_vals in res:
            po_line_id = move_vals.get('purchase_line_id')
            po_line = self.order_line.filtered(lambda l: l.id == po_line_id)

            if po_line:
                _logger.info(f"[MARBLE-FIX] Línea PO encontrada: ID {po_line.id} → altura={po_line.marble_height}, ancho={po_line.marble_width}, m²={po_line.marble_sqm}, lote={po_line.lot_general}")
                move_vals.update({
                    'marble_height': po_line.marble_height or 0.0,
                    'marble_width': po_line.marble_width or 0.0,
                    'marble_sqm': po_line.marble_sqm or 0.0,
                    'marble_thickness': po_line.marble_thickness or 0.0,
                    'lot_general': po_line.lot_general or '',


                })
            else:
                _logger.warning(f"[MARBLE-FIX] No se encontró línea PO para move_vals: {move_vals}")
        return res
