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

    # ---------- Datos de mármol (EDITABLES) ----------
    marble_height = fields.Float(
        string='Altura (m)',
        store=True,
        readonly=False  # CAMBIADO: Ahora es editable
    )
    marble_width = fields.Float(
        string='Ancho (m)',
        store=True,
        readonly=False  # CAMBIADO: Ahora es editable
    )
    marble_sqm = fields.Float(
        string='m²',
        compute='_compute_marble_sqm',
        store=True,
        readonly=False  # CAMBIADO: Ahora es editable
    )
    lot_general = fields.Char(
        string='Lote',
        store=True,
        readonly=False  # CAMBIADO: Ahora es editable
    )
   
    marble_thickness = fields.Float(
        string='Grosor (cm)',
        store=True,
        readonly=False  # CAMBIADO: Ahora es editable
    )

    # =====================================================
    # LÓGICA ACTUALIZADA
    # =====================================================

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        """
        Calcula automáticamente los m² cuando se modifican altura o ancho
        """
        for line in self:
            if line.marble_height and line.marble_width:
                line.marble_sqm = line.marble_height * line.marble_width
            elif not line.lot_id:
                # Solo resetear si no hay lote seleccionado
                line.marble_sqm = 0.0

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """
        Cuando se selecciona un lote, actualizar los campos con los valores del lote
        """
        if self.lot_id:
            self.marble_height = self.lot_id.marble_height
            self.marble_width = self.lot_id.marble_width
            self.marble_sqm = self.lot_id.marble_sqm
            self.lot_general = self.lot_id.lot_general
            self.marble_thickness = self.lot_id.marble_thickness
            
            _logger.info(f"[LOT-CHANGE] Campos actualizados desde lote {self.lot_id.name}")

    @api.depends('lot_id')
    def _compute_pedimento_number(self):
        """
        Cuando el usuario selecciona un lote, buscamos cualquier quant
        (con existencias positivas) que tenga asignado un pedimento.
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

# ---------- Propagación al procurement MEJORADA ----------
    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id)
        
        # LOGGING para debug - ver qué valores tenemos en la línea de venta
        _logger.info(f"[PROCUREMENT-VALUES-DEBUG] SO Line {self.id}:")
        _logger.info(f"  - marble_height: {self.marble_height}")
        _logger.info(f"  - marble_width: {self.marble_width}")
        _logger.info(f"  - marble_sqm: {self.marble_sqm}")
        _logger.info(f"  - lot_general: {self.lot_general}")
        _logger.info(f"  - marble_thickness: {self.marble_thickness}")
        _logger.info(f"  - lot_id: {self.lot_id.id if self.lot_id else 'None'}")
        
        # Solo propagar lot_id si existe
        if self.lot_id:
            vals['lot_id'] = self.lot_id.id
            
        # PROPAGAR SIEMPRE los campos de mármol, incluso si son 0.0 o vacíos
        # Esto es crítico para MTO cuando vendes "metros cuadrados sin dimensiones específicas"
        vals.update({
            'marble_height':    self.marble_height or 0.0,
            'marble_width':     self.marble_width or 0.0,
            'marble_sqm':       self.marble_sqm or 0.0,
            'lot_general':      self.lot_general or '',
            'pedimento_number': self.pedimento_number or '',
            'marble_thickness': self.marble_thickness or 0.0,
        })
        
        # LOGGING para ver qué se está enviando al procurement
        _logger.info(f"[PROCUREMENT-VALUES-DEBUG] Valores enviados al procurement: {vals}")
        
        return vals
    
    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
        Sobrescribir para asegurar que cada línea genere su propio procurement
        """
        # Procesar cada línea individualmente
        for line in self:
            # Si el producto tiene tracking, crear un grupo único para cada línea
            if line.product_id.tracking != 'none':
                # Crear un grupo de procurement único para esta línea
                group = self.env['procurement.group'].create({
                    'name': f"{line.order_id.name}/{line.id}",
                    'sale_id': line.order_id.id,
                    'partner_id': line.order_id.partner_id.id,
                })
                
                # Forzar el uso de este grupo específico
                line_with_context = line.with_context(default_group_id=group.id)
                
                _logger.info(f"Creando procurement individual para línea {line.id} con grupo {group.name}")
                
                # Llamar al método padre para esta línea específica
                super(SaleOrderLine, line_with_context)._action_launch_stock_rule(previous_product_uom_qty)
            else:
                # Para productos sin tracking, usar el comportamiento normal
                super(SaleOrderLine, line)._action_launch_stock_rule(previous_product_uom_qty)
        
        return True