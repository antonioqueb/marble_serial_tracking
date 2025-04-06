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
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)

        _logger.info("=== INICIO _prepare_stock_move_vals ===")
        _logger.info(f"Contexto actual: {self.env.context}")
        _logger.info(f"ID del self: {self.id}")
        _logger.info(f"Self.raw: {self.read(['marble_height', 'marble_width', 'marble_sqm', 'lot_general'])}")

        # Si el registro ya existe en la BD, usamos browse para obtener datos confiables
        record = self.browse(self.id) if self.id else self

        _logger.info(f"Registro leído con browse({self.id}): {record.read(['marble_height', 'marble_width', 'marble_sqm', 'lot_general'])}")
        _logger.info(f"Propagando desde PO line: ID {record.id}, marble_height={record.marble_height}, marble_width={record.marble_width}, marble_sqm={record.marble_sqm}, lot_general={record.lot_general}")

        vals.update({
            'marble_height': record.marble_height or 0.0,
            'marble_width': record.marble_width or 0.0,
            'marble_sqm': record.marble_sqm or 0.0,
            'lot_general': record.lot_general or '',
        })

        _logger.info(f"Valores finales enviados a move: {vals}")
        _logger.info("=== FIN _prepare_stock_move_vals ===")
        return vals
