from odoo import models, fields, api
import logging

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
                altura = po_line.marble_height or 0.0
                ancho = po_line.marble_width or 0.0
                marble_sqm = po_line.marble_sqm

                # Lógica robusta para marble_sqm
                if altura > 0 and ancho > 0:
                    marble_sqm = altura * ancho
                    _logger.debug(f"[MARBLE-FIX] Recalculado m² basado en altura x ancho: {marble_sqm}")
                elif marble_sqm > 0:
                    _logger.debug(f"[MARBLE-FIX] Manteniendo valor original de marble_sqm: {marble_sqm}")
                else:
                    marble_sqm = 0.0
                    _logger.debug(f"[MARBLE-FIX] Sin dimensiones ni valor original, marble_sqm establecido en 0")

                move_vals.update({
                    'marble_height': altura,
                    'marble_width': ancho,
                    'marble_sqm': marble_sqm,
                    'marble_thickness': po_line.marble_thickness or 0.0,
                    'lot_general': po_line.lot_general or '',
                })

                _logger.info(
                    f"[MARBLE-FIX] Línea PO encontrada: ID {po_line.id} → altura={altura}, "
                    f"ancho={ancho}, m²={marble_sqm}, lote={po_line.lot_general}"
                )
            else:
                _logger.warning(f"[MARBLE-FIX] No se encontró línea PO para move_vals: {move_vals}")

        return res