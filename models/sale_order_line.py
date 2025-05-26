# models/sale_order_line.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ---------- Selección de lote solo entre lotes DISPONIBLES ----------
    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie',
        domain="[('id', 'in', available_lot_ids)]",
    )

    available_lot_ids = fields.Many2many(
        'stock.lot',
        string='Lotes Disponibles',
        compute='_compute_available_lots',
    )

    @api.depends('product_id')
    def _compute_available_lots(self):
        """
        Solo mostrar lotes con inventario disponible y en ubicaciones internas.
        """
        Quant = self.env['stock.quant']
        for line in self:
            if line.product_id:
                quants = Quant.search([
                    ('product_id', '=', line.product_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                    ('lot_id', '!=', False),
                ])
                line.available_lot_ids = quants.mapped('lot_id')
            else:
                line.available_lot_ids = False

    # ---------- Número de pedimento ----------
    pedimento_number = fields.Char(
        string='Número de Pedimento',
        size=18,
        compute='_compute_pedimento_number',
        store=True,
        readonly=True,
    )

    # ---------- Datos de mármol (ya existentes, relacionados con el lote) ----------
    # Cambiar de related a compute para manejar cuando no hay lote
    marble_height = fields.Float(
        string='Altura (m)',
        compute='_compute_marble_fields',
        store=True,
        readonly=True
    )
    marble_width = fields.Float(
        string='Ancho (m)',
        compute='_compute_marble_fields',
        store=True,
        readonly=True
    )
    marble_sqm = fields.Float(
        string='Metros Cuadrados',
        compute='_compute_marble_fields',
        store=True,
        readonly=True
    )
    lot_general = fields.Char(
        string='Lote General',
        compute='_compute_marble_fields',
        store=True,
        readonly=True
    )
    bundle_code = fields.Char(
        string='Bundle Code',
        compute='_compute_marble_fields',
        store=True,
        readonly=True
    )
    marble_thickness = fields.Float(
        string='Grosor (cm)',
        compute='_compute_marble_fields',
        store=True,
        readonly=True
    )

    # =====================================================
    # LÓGICA
    # =====================================================

    @api.depends('lot_id')
    def _compute_marble_fields(self):
        """
        Si hay lote, toma los valores del lote.
        Si no hay lote, establece valores por defecto.
        """
        for line in self:
            if line.lot_id:
                line.marble_height = line.lot_id.marble_height
                line.marble_width = line.lot_id.marble_width
                line.marble_sqm = line.lot_id.marble_sqm
                line.lot_general = line.lot_id.lot_general
                line.bundle_code = line.lot_id.bundle_code
                line.marble_thickness = line.lot_id.marble_thickness
            else:
                line.marble_height = 0.0
                line.marble_width = 0.0
                line.marble_sqm = 0.0
                line.lot_general = ''
                line.bundle_code = ''
                line.marble_thickness = 0.0

    @api.depends('lot_id')
    def _compute_pedimento_number(self):
        """
        Cuando el usuario selecciona un lote, buscamos cualquier quant
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

    @api.constrains('lot_id', 'product_id')
    def _check_lot_requirement(self):
        """
        Validación: Si hay stock disponible, debe seleccionarse un lote
        Solo aplica si el producto usa tracking
        """
        for line in self:
            if line.product_id and line.product_id.tracking != 'none':
                if line.available_lot_ids and not line.lot_id:
                    raise ValidationError(
                        _('El producto "%s" tiene stock disponible. '
                          'Debe seleccionar un lote específico.') % line.product_id.name
                    )

    # ---------- Propagación al procurement ----------
    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id)
        
        # Solo propagar lot_id si existe
        if self.lot_id:
            vals['lot_id'] = self.lot_id.id
            
        vals.update({
            'marble_height':    self.marble_height,
            'marble_width':     self.marble_width,
            'marble_sqm':       self.marble_sqm,
            'lot_general':      self.lot_general,
            'bundle_code':      self.bundle_code,
            'pedimento_number': self.pedimento_number,
            'marble_thickness': self.marble_thickness,
        })
        return vals