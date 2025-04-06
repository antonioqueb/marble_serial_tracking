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
            line.marble_sqm = line.marble_height * line.marble_width

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        _logger.info(f"[MARBLE-TEST] Ejecutando _prepare_stock_move_vals en PO Line ID {self.id}")
        _logger.info(f"[MARBLE-TEST] Datos actuales: marble_height={self.marble_height}, marble_width={self.marble_width}, marble_sqm={self.marble_sqm}, lot_general={self.lot_general}")

        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)

        _logger.info(f"[MARBLE-TEST] Valores heredados del super(): {vals}")

        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
        })

        _logger.info(f"[MARBLE-TEST] Valores finales enviados al stock.move: {vals}")
        return vals

    def _create_stock_moves(self, picking):
        _logger.info(f"[MARBLE-TEST] Ejecutando _create_stock_moves en PO Line ID {self.id}")
        moves = super()._create_stock_moves(picking)

        _logger.info(f"[MARBLE-TEST] Total moves creados: {len(moves)}")
        for move in moves:
            _logger.info(f"[MARBLE-TEST] Move ID {move.id} creado para producto: {move.product_id.display_name}")
        return moves
