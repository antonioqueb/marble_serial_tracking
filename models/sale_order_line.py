# models/sale_order_line.py
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ---------- Selección de lote ----------
    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie',
        domain="[('product_id', '=', product_id)]",
    )

    # ---------- Número de pedimento ----------
    pedimento_number = fields.Char(
        string='Número de Pedimento',
        size=18,
        compute='_compute_pedimento_number',
        store=True,
        readonly=True,
    )

    # ---------- Datos de mármol (ya existentes) ----------
    marble_height = fields.Float(related='lot_id.marble_height', store=True, readonly=True)
    marble_width  = fields.Float(related='lot_id.marble_width',  store=True, readonly=True)
    marble_sqm    = fields.Float(related='lot_id.marble_sqm',    store=True, readonly=True)
    lot_general   = fields.Char (related='lot_id.lot_general',   store=True, readonly=True)
    bundle_code   = fields.Char (related='lot_id.bundle_code',   store=True, readonly=True)
    marble_thickness = fields.Float(related='lot_id.marble_thickness', store=True, readonly=True)
    # =====================================================
    # LÓGICA
    # =====================================================

    @api.depends('lot_id')
    def _compute_pedimento_number(self):
        """
        Cuando el usuario selecciona un lote buscamos cualquier quant
        (con existencias positivas) que tenga asignado un pedimento.
        Tomamos el primero que aparezca ―es el mismo valor para todas
        las existencias del lote― y lo almacenamos en la línea.
        """
        Quant = self.env['stock.quant']
        for line in self:
            ped = False
            if line.lot_id:
                quant = Quant.search([
                    ('lot_id', '=', line.lot_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', 'in', ['internal', 'transit']),
                ], limit=1, order='in_date DESC')
                ped = quant.pedimento_number or False
            line.pedimento_number = ped
            _logger.debug(
                "[PED-SAL] SO Line %s → lote=%s → pedimento=%s",
                line.id, line.lot_id.name if line.lot_id else '-', ped or '∅'
            )

    # ---------- Propagación al procurement ----------
    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id)
        vals.update({
            'lot_id':           self.lot_id.id,
            'marble_height':    self.marble_height,
            'marble_width':     self.marble_width,
            'marble_sqm':       self.marble_sqm,
            'lot_general':      self.lot_general,
            'bundle_code':      self.bundle_code,
            'pedimento_number': self.pedimento_number,
            'marble_thickness': self.marble_thickness,
        })
        return vals
