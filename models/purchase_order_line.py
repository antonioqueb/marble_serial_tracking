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

    def _create_stock_moves(self, picking):
        """Sobrescribe el método que genera los stock.move para asegurar
        que se propaguen los campos personalizados desde la orden de compra."""
        self.ensure_one()
        moves = super()._create_stock_moves(picking)

        _logger.info("=== INICIO _create_stock_moves ===")
        _logger.info(f"PO Line ID: {self.id}")
        _logger.info(f"Valores personalizados en línea de compra: "
                     f"marble_height={self.marble_height}, marble_width={self.marble_width}, "
                     f"marble_sqm={self.marble_sqm}, lot_general={self.lot_general}")

        for move in moves:
            move.write({
                'marble_height': self.marble_height or 0.0,
                'marble_width': self.marble_width or 0.0,
                'marble_sqm': self.marble_sqm or 0.0,
                'lot_general': self.lot_general or '',
            })
            _logger.info(f"Campos escritos en move_id={move.id}: "
                         f"height={self.marble_height}, width={self.marble_width}, "
                         f"sqm={self.marble_sqm}, lote={self.lot_general}")
        _logger.info("=== FIN _create_stock_moves ===")

        return moves
