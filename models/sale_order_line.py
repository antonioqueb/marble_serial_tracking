# models/sale_order_line.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # --- INICIO: CAMPOS DE sale_order_line_pricing.py ---
    price_level = fields.Selection(
        [
            ('max', 'Precio Máximo'),
            ('avg', 'Precio Promedio'),
            ('min', 'Precio Mínimo'),
            ('manual', 'Manual')
        ],
        string='Nivel de Precio',
        default='max'
    )
    applied_price_per_sqm = fields.Float(
        string='Precio por m² Aplicado',
        digits='Product Price',
        readonly=False
    )
    # --- FIN: CAMPOS DE sale_order_line_pricing.py ---

    # --- INICIO: CAMPOS DE sale_order_line.py ---
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
    numero_contenedor = fields.Char(string='Número de Contenedor', store=True, readonly=False)
    pedimento_number = fields.Char(
        string='Número de Pedimento',
        size=18,
        compute='_compute_pedimento_number',
        store=True,
        readonly=True,
    )
    marble_height    = fields.Float(string='Altura (m)',   store=True, readonly=False)
    marble_width     = fields.Float(string='Ancho (m)',    store=True, readonly=False)
    marble_sqm       = fields.Float(string='m²',           compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general      = fields.Char(string='Lote',          store=True, readonly=False)
    marble_thickness = fields.Float(string='Grosor (cm)',  store=True, readonly=False)
    # --- FIN: CAMPOS DE sale_order_line.py ---


    # --- INICIO: MÉTODOS DE sale_order_line_pricing.py ---
    @api.onchange('lot_id', 'price_level')
    def _onchange_lot_pricing(self):
        """
        Ajusta applied_price_per_sqm y price_unit según el lote y nivel seleccionado,
        salvo en modo manual.
        """
        for line in self:
            if line.lot_id and line.product_id and line.price_level != 'manual':
                if line.price_level == 'max':
                    price_per_sqm = line.product_id.price_per_sqm_max
                elif line.price_level == 'avg':
                    price_per_sqm = line.product_id.price_per_sqm_avg
                else:
                    price_per_sqm = line.product_id.price_per_sqm_min

                line.applied_price_per_sqm = price_per_sqm or 0.0

                if price_per_sqm and line.marble_sqm:
                    line.price_unit = line.marble_sqm * price_per_sqm
            elif line.price_level == 'manual':
                pass
            else:
                line.applied_price_per_sqm = 0.0

    @api.onchange('applied_price_per_sqm', 'marble_sqm')
    def _onchange_manual_pricing(self):
        """
        Recalcula price_unit si se modifica manualmente applied_price_per_sqm o marble_sqm.
        """
        for line in self:
            if line.applied_price_per_sqm and line.marble_sqm:
                line.price_unit = line.marble_sqm * line.applied_price_per_sqm

    @api.onchange('price_level')
    def _onchange_price_level_mode(self):
        """
        Muestra advertencia al activar modo manual.
        """
        if self.price_level == 'manual':
            return {
                'warning': {
                    'title': 'Modo Manual Activado',
                    'message': (
                        'Ahora puedes editar directamente el precio por m². '
                        'El precio unitario se calculará automáticamente.'
                    )
                }
            }
    # --- FIN: MÉTODOS DE sale_order_line_pricing.py ---


    # --- INICIO: MÉTODOS DE sale_order_line.py ---
    @api.depends('product_id')
    def _compute_available_lots(self):
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

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            if line.marble_height and line.marble_width:
                line.marble_sqm = line.marble_height * line.marble_width
            elif not line.lot_id:
                line.marble_sqm = 0.0

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id:
            self.marble_height    = self.lot_id.marble_height
            self.marble_width     = self.lot_id.marble_width
            self.marble_sqm       = self.lot_id.marble_sqm
            self.lot_general      = self.lot_id.lot_general
            self.marble_thickness = self.lot_id.marble_thickness
            self.numero_contenedor = self.lot_id.numero_contenedor

    @api.depends('lot_id')
    def _compute_pedimento_number(self):
        Quant = self.env['stock.quant']
        for line in self:
            if line.lot_id:
                quant = Quant.search([
                    ('lot_id', '=', line.lot_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', 'in', ['internal', 'transit']),
                ], limit=1, order='in_date DESC')
                line.pedimento_number = quant.pedimento_number or ''
            else:
                line.pedimento_number = ''

    @api.constrains('lot_id', 'product_id')
    def _check_lot_requirement(self):
        for line in self:
            if line.product_id and line.product_id.tracking != 'none':
                is_mto = any(
                    rule.action == 'buy' and rule.procure_method == 'make_to_order'
                    for route in line.product_id.route_ids
                    for rule in route.rule_ids
                )
                if is_mto:
                    continue
                
                # LA LÓGICA CLAVE ESTÁ AQUÍ Y ESTÁ CORRECTA
                if line.product_id.require_lot_selection_on_sale and line.available_lot_ids and not line.lot_id:
                    raise ValidationError(_(
                        'El producto "%s" tiene stock disponible. '
                        'Debe seleccionar un lote específico.'
                    ) % line.product_id.name)

    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id)
        if self.lot_id:
            vals['lot_id'] = self.lot_id.id
        vals.update({
            'marble_height':    self.marble_height or 0.0,
            'marble_width':     self.marble_width or 0.0,
            'marble_sqm':       self.marble_sqm or 0.0,
            'lot_general':      self.lot_general or '',
            'pedimento_number': self.pedimento_number or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'sale_line_id':     self.id,
            'numero_contenedor': self.numero_contenedor or '',
        })
        return vals

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        for line in self:
            if line.product_id.tracking != 'none' or line.marble_sqm > 0:
                group = self.env['procurement.group'].create({
                    'name':        f"{line.order_id.name}/L{line.id}",
                    'sale_id':     line.order_id.id,
                    'partner_id':  line.order_id.partner_id.id,
                })
                proc_values = line._prepare_procurement_values(group_id=group.id)
                proc_values.update({
                    'marble_height':    line.marble_height,
                    'marble_width':     line.marble_width,
                    'marble_sqm':       line.marble_sqm,
                    'lot_general':      line.lot_general,
                    'marble_thickness': line.marble_thickness,
                    'pedimento_number': line.pedimento_number,
                    'lot_id':           line.lot_id.id if line.lot_id else False,
                    'sale_line_id':     line.id,
                    'numero_contenedor': line.numero_contenedor,
                })
                line_with_context = line.with_context(
                    default_group_id=group.id,
                    force_procurement_values=proc_values
                )
                super(SaleOrderLine, line_with_context)._action_launch_stock_rule(previous_product_uom_qty)
            else:
                super(SaleOrderLine, line)._action_launch_stock_rule(previous_product_uom_qty)
        return True
    # --- FIN: MÉTODOS DE sale_order_line.py ---