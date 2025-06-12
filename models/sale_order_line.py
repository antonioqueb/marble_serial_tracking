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

    # ---------- Datos de mármol (EDITABLES) ----------
    marble_height = fields.Float(string='Altura (m)', store=True, readonly=False)
    marble_width = fields.Float(string='Ancho (m)', store=True, readonly=False)
    marble_sqm = fields.Float(string='m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char(string='Lote', store=True, readonly=False)
    marble_thickness = fields.Float(string='Grosor (cm)', store=True, readonly=False)

    # =====================================================
    # LÓGICA ACTUALIZADA
    # =====================================================

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
            self.marble_height = self.lot_id.marble_height
            self.marble_width = self.lot_id.marble_width
            self.marble_sqm = self.lot_id.marble_sqm
            self.lot_general = self.lot_id.lot_general
            self.marble_thickness = self.lot_id.marble_thickness

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
                if line.available_lot_ids and not line.lot_id:
                    raise ValidationError(_(
                        'El producto "%s" tiene stock disponible. '
                        'Debe seleccionar un lote específico.'
                    ) % line.product_id.name)

    # ---------- Propagación al procurement ----------
    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id)
        
        _logger.info(f"[SALE-PROCUREMENT] Línea {self.id} - Preparando valores para procurement:")
        _logger.info(f"  - Producto: {self.product_id.name}")
        _logger.info(f"  - Lote: {self.lot_id.name if self.lot_id else 'Sin lote'}")
        _logger.info(f"  - Dimensiones: {self.marble_height}x{self.marble_width} = {self.marble_sqm}m²")
        _logger.info(f"  - Lote General: {self.lot_general}")
        _logger.info(f"  - Pedimento: {self.pedimento_number}")
        
        # Solo propagar lot_id si existe
        if self.lot_id:
            vals['lot_id'] = self.lot_id.id
        # Propagar siempre datos de mármol y pedimento
        vals.update({
            'marble_height':    self.marble_height or 0.0,
            'marble_width':     self.marble_width or 0.0,
            'marble_sqm':       self.marble_sqm or 0.0,
            'lot_general':      self.lot_general or '',
            'pedimento_number': self.pedimento_number or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'sale_line_id':     self.id,
        })
        
        _logger.info(f"[SALE-PROCUREMENT] Valores finales para procurement: {vals}")
        return vals

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
        Sobrescribir para asegurar que cada línea genere su propio procurement
        y mantenga la trazabilidad correcta
        """
        _logger.info(f"[LAUNCH-STOCK-RULE] Iniciando para {len(self)} líneas de venta")
        
        for line in self:
            _logger.info(f"[LAUNCH-STOCK-RULE] Procesando línea {line.id}:")
            _logger.info(f"  - Producto: {line.product_id.name}")
            _logger.info(f"  - Tracking: {line.product_id.tracking}")
            _logger.info(f"  - Lote: {line.lot_id.name if line.lot_id else 'Sin lote'}")
            _logger.info(f"  - m²: {line.marble_sqm}")
            
            if line.product_id.tracking != 'none' or line.marble_sqm > 0:
                # Crear grupo de procurement único
                group = self.env['procurement.group'].create({
                    'name': f"{line.order_id.name}/L{line.id}",
                    'sale_id': line.order_id.id,
                    'partner_id': line.order_id.partner_id.id,
                })
                
                _logger.info(f"[LAUNCH-STOCK-RULE] Grupo único creado: {group.name}")
                
                # Preparar valores con todos los datos
                proc_values = line._prepare_procurement_values(group_id=group.id)
                
                # Asegurar que todos los campos estén presentes
                proc_values.update({
                    'marble_height': line.marble_height,
                    'marble_width': line.marble_width,
                    'marble_sqm': line.marble_sqm,
                    'lot_general': line.lot_general,
                    'marble_thickness': line.marble_thickness,
                    'pedimento_number': line.pedimento_number,
                    'lot_id': line.lot_id.id if line.lot_id else False,
                    'sale_line_id': line.id,
                })
                
                _logger.info(f"[LAUNCH-STOCK-RULE] Valores completos para procurement: {proc_values}")
                
                # Forzar contexto con los valores preparados
                line_with_context = line.with_context(
                    default_group_id=group.id,
                    force_procurement_values=proc_values
                )
                
                # Llamar al método padre para esta línea específica
                super(SaleOrderLine, line_with_context)._action_launch_stock_rule(previous_product_uom_qty)
                
                _logger.info(f"[LAUNCH-STOCK-RULE] Stock rule ejecutada para línea {line.id}")
            else:
                _logger.info(f"[LAUNCH-STOCK-RULE] Usando comportamiento estándar para línea {line.id}")
                super(SaleOrderLine, line)._action_launch_stock_rule(previous_product_uom_qty)
        
        _logger.info("[LAUNCH-STOCK-RULE] Proceso completado para todas las líneas")
        return True