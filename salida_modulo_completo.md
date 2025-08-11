-e ### ./data/ir_sequence_data.xml
```
<odoo noupdate="1">
</odoo>
```

-e ### ./models/procurement_group.py
```
from odoo import models, api

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _run_buy(self, procurements):  # procurements es una lista de tuplas (procurement_request, rule)
        procurement_data_to_apply = {}  # {proc_key: marble_data_dict}
        # Nuevo: mapeo de proc_key a los valores originales del procurement_request para _prepare_purchase_order_line
        original_proc_values_map = {}

        # BUCLE 1: Extraer y almacenar los datos de mármol
        for procurement_request, rule in procurements:
            if not hasattr(procurement_request, 'product_id') or \
               not hasattr(procurement_request, 'origin') or \
               not hasattr(procurement_request, 'values'):
                continue

            product_record = procurement_request.product_id
            origin_str = procurement_request.origin  # Este es el SO (ej. S00002)

            # procurement_request.values es el diccionario de valores que llega a _run_buy.
            current_proc_values = procurement_request.values or {}

            proc_key = f"{product_record.id}_{origin_str}"
            original_proc_values_map[proc_key] = current_proc_values  # Guardamos los valores que SÍ llegan

            marble_data_found = {}

            # Intento 1: ¿Están los campos de mármol directamente en current_proc_values?
            if 'marble_sqm' in current_proc_values and current_proc_values.get('marble_sqm', 0.0) > 0:
                marble_data_found = {
                    'marble_height': current_proc_values.get('marble_height', 0.0),
                    'marble_width': current_proc_values.get('marble_width', 0.0),
                    'marble_sqm': current_proc_values.get('marble_sqm', 0.0),
                    'lot_general': current_proc_values.get('lot_general', ''),
                    'marble_thickness': current_proc_values.get('marble_thickness', 0.0),
                    'numero_contenedor': current_proc_values.get('numero_contenedor', ''),
                }

            # Intento 2: Si no, intentar obtenerlos del stock.move de origen (move_dest_ids)
            if not marble_data_found and 'move_dest_ids' in current_proc_values and current_proc_values['move_dest_ids']:
                source_moves = current_proc_values['move_dest_ids']
                if isinstance(source_moves, models.BaseModel) and source_moves._name == 'stock.move':
                    first_move = source_moves[0] if source_moves else None
                    if first_move and first_move.marble_sqm > 0:  # Chequeamos si el move tiene los m2
                        marble_data_found = {
                            'marble_height': first_move.marble_height,
                            'marble_width': first_move.marble_width,
                            'marble_sqm': first_move.marble_sqm,
                            'lot_general': first_move.lot_general,
                            'marble_thickness': first_move.marble_thickness,
                            'numero_contenedor': first_move.numero_contenedor,
                            
                        }
                        # IMPORTANTE: Añadir estos datos al diccionario original_proc_values_map[proc_key]
                        original_proc_values_map[proc_key].update(marble_data_found)

            if marble_data_found:
                procurement_data_to_apply[proc_key] = marble_data_found

        # Pasar el mapa de valores originales al contexto para que _prepare_purchase_order_line lo use
        self_with_context = self.with_context(original_proc_values_map=original_proc_values_map)

        res = super(StockRule, self_with_context)._run_buy(procurements)  # Llamar a super con el contexto modificado

        # BUCLE 2: Aplicar/Reafirmar los datos de mármol a las PO Lines.
        if procurement_data_to_apply:
            for procurement_request, rule in procurements:
                if not hasattr(procurement_request, 'product_id') or not hasattr(procurement_request, 'origin'):
                    continue
                product_record = procurement_request.product_id
                origin_str = procurement_request.origin
                proc_key = f"{product_record.id}_{origin_str}"

                if proc_key in procurement_data_to_apply:
                    marble_data = procurement_data_to_apply[proc_key]
                    current_proc_values = procurement_request.values or {}
                    move_dest_ids_val = current_proc_values.get('move_dest_ids')

                    if move_dest_ids_val:
                        actual_move_ids = []
                        # Asegurarse de que move_dest_ids_val es un iterable de IDs
                        if isinstance(move_dest_ids_val, models.BaseModel):  # Si es un recordset
                            actual_move_ids = move_dest_ids_val.ids
                        elif isinstance(move_dest_ids_val, (list, tuple)) and all(isinstance(i, int) for i in move_dest_ids_val):  # Si es una lista/tupla de IDs
                            actual_move_ids = list(move_dest_ids_val)
                        elif isinstance(move_dest_ids_val, int):  # Si es un solo ID
                            actual_move_ids = [move_dest_ids_val]

                        if not actual_move_ids:
                            continue

                        po_lines = self.env['purchase.order.line'].search([
                            ('move_dest_ids', 'in', actual_move_ids)
                        ])

                        if po_lines:
                            for po_line in po_lines:
                                po_line.with_context(from_procurement=True).write(marble_data)
        return res

    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        origin_str = values.get('origin')  # El origin del procurement_request
        proc_key = f"{product_id.id}_{origin_str}"

        original_proc_values_map = self.env.context.get('original_proc_values_map', {})
        # Usar los valores enriquecidos del mapa si existen para esta clave, sino los 'values' directos.
        values_for_po_line = original_proc_values_map.get(proc_key, values)

        # Llamar a super con los 'values' originales.
        res_vals = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)

        marble_fields_to_set = {}
        # Ahora usamos 'values_for_po_line' que debería tener los datos de mármol.
        if values_for_po_line.get('marble_sqm', 0.0) > 0:  # Condición principal para aplicar datos de mármol
            marble_fields_to_set['marble_sqm'] = values_for_po_line.get('marble_sqm', 0.0)
            marble_fields_to_set['marble_height'] = values_for_po_line.get('marble_height', 0.0)
            marble_fields_to_set['marble_width'] = values_for_po_line.get('marble_width', 0.0)
            marble_fields_to_set['lot_general'] = values_for_po_line.get('lot_general', '')
            marble_fields_to_set['marble_thickness'] = values_for_po_line.get('marble_thickness', 0.0)
            marble_fields_to_set['numero_contenedor'] = values_for_po_line.get('numero_contenedor', '')
        if marble_fields_to_set:
            res_vals.update(marble_fields_to_set)

        return res_vals
```

-e ### ./models/product_template.py
```
# models/product_template.py
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Precios por metro cuadrado
    price_per_sqm_min = fields.Float(
        string='Precio Mínimo por m²',
        digits='Product Price',
        help='Precio mínimo de venta por metro cuadrado'
    )
    
    price_per_sqm_avg = fields.Float(
        string='Precio Promedio por m²',
        digits='Product Price',
        help='Precio promedio de venta por metro cuadrado'
    )
    
    price_per_sqm_max = fields.Float(
        string='Precio Máximo por m²',
        digits='Product Price',
        help='Precio máximo de venta por metro cuadrado'
    )

    # --- INICIO DEL CAMBIO ---
    # Añade este nuevo campo
    require_lot_selection_on_sale = fields.Boolean(
        string="Exigir Lote Específico en Venta",
        default=True,
        help="Si se marca, será obligatorio seleccionar un número de lote/serie en la orden de venta si hay stock disponible.
"
             "Desmarcar para productos (como porcelanato) donde el lote se puede asignar durante el picking en el almacén."
    )
    # --- FIN DEL CAMBIO ---
```

-e ### ./models/purchase_order_line.py
```
# models/purchase_order_line.py

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    marble_height = fields.Float('Altura (m)', store=True)
    marble_width = fields.Float('Ancho (m)', store=True)
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote', store=True)
    marble_thickness = fields.Float('Grosor (cm)')
    numero_contenedor = fields.Char('Número de Contenedor', store=True)

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        """
        Lógica de cálculo HÍBRIDA:
        - Si se especifican altura y ancho, calcula los m².
        - Si NO se especifican, NO HACE NADA, permitiendo que el valor
          introducido manualmente por el usuario se conserve.
        """
        for line in self:
            if line.marble_height > 0 and line.marble_width > 0:
                line.marble_sqm = line.marble_height * line.marble_width

    @api.onchange('marble_height', 'marble_width', 'lot_general')
    def _onchange_marble_fields(self):
        return

    def write(self, vals):
        res = super().write(vals)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        return lines

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        self.ensure_one()
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        
        _logger.info("🔍 DEBUG: _prepare_stock_move_vals para línea PO %s", self.id)
        _logger.info("🔍 DEBUG: Producto: %s, Cantidad: %s", self.product_id.name, product_uom_qty)
        _logger.info("🔍 DEBUG: Datos mármol - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                    self.marble_height, self.marble_width, self.marble_sqm, self.lot_general)
        
        # CLAVE: Añadir un identificador único para evitar agrupación
        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'numero_contenedor': self.numero_contenedor or '',
            # Añadir referencia única a la línea de compra para evitar agrupación
            'purchase_line_id': self.id,
            'origin': f"{self.order_id.name} - Línea {self.id}",
        })
        
        _logger.info("🔍 DEBUG: Stock move vals preparados: %s", vals)
        return vals

    def _create_stock_moves(self, picking):
        """
        Sobrescribir para asegurar que cada línea genera su propio move independiente
        """
        _logger.info("🚀 DEBUG: _create_stock_moves llamado para %s líneas", len(self))
        
        moves = self.env['stock.move']
        
        for line in self:
            _logger.info("🔄 DEBUG: Procesando línea PO %s - Producto: %s", line.id, line.product_id.name)
            _logger.info("🔄 DEBUG: Datos línea - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        line.marble_height, line.marble_width, line.marble_sqm, line.lot_general)
            
            # Crear un move individual para cada línea
            move_vals = line._prepare_stock_move_vals(
                picking, 
                line.price_unit, 
                line.product_qty, 
                line.product_uom
            )
            
            # Asegurar que el move tenga un nombre único
            move_vals['name'] = f"{line.order_id.name} - {line.product_id.name} - Línea {line.id}"
            
            _logger.info("🔄 DEBUG: Creando move con vals: %s", move_vals)
            
            move = self.env['stock.move'].create(move_vals)
            moves |= move
            
            _logger.info("✅ DEBUG: Move creado ID: %s - Nombre: %s", move.id, move.name)
            _logger.info("✅ DEBUG: Move datos - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
            
        _logger.info("🏁 DEBUG: Total moves creados: %s", len(moves))
        return moves

    def _get_stock_move_map(self):
        """
        Sobrescribir para evitar que Odoo agrupe movimientos por producto
        """
        _logger.info("🗺️ DEBUG: _get_stock_move_map llamado para %s líneas", len(self))
        
        # En lugar de agrupar por producto, crear un mapeo único por línea
        move_map = {}
        for line in self:
            # Usar el ID de la línea como clave única
            key = f"line_{line.id}_{line.product_id.id}"
            move_map[key] = {
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'lines': [line],
            }
            _logger.info("🗺️ DEBUG: Mapeando línea %s con clave única: %s", line.id, key)
        
        _logger.info("🗺️ DEBUG: Move map final: %s", move_map)
        return move_map
```

-e ### ./models/purchase_order.py
```
# models/purchase_order.py

from odoo import models
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _prepare_stock_moves(self, picking):
        """
        Sobrescribir para asegurar que cada línea de PO genere su propio move
        """
        self.ensure_one()
        _logger.info("🏭 DEBUG: PurchaseOrder._prepare_stock_moves para orden %s", self.name)
        _logger.info("🏭 DEBUG: Número de líneas en la orden: %s", len(self.order_line))
        
        res = []

        for line in self.order_line:
            _logger.info("📋 DEBUG: Procesando línea orden %s - Producto: %s", line.id, line.product_id.name)
            
            # Crear un move individual para cada línea
            move_vals = line._prepare_stock_move_vals(
                picking, 
                line.price_unit, 
                line.product_qty, 
                line.product_uom
            )
            
            # Asegurar nombre único y datos de mármol
            altura = line.marble_height or 0.0
            ancho = line.marble_width or 0.0
            marble_sqm = line.marble_sqm

            # Recalcula o ajusta marble_sqm según dimensiones
            if altura > 0 and ancho > 0:
                marble_sqm = altura * ancho
            elif not marble_sqm:
                marble_sqm = 0.0

            move_vals.update({
                'name': f"{self.name} - {line.product_id.name} [Línea {line.id}]",
                'marble_height': altura,
                'marble_width': ancho,
                'marble_sqm': marble_sqm,
                'marble_thickness': line.marble_thickness or 0.0,
                'lot_general': line.lot_general or '',
                'numero_contenedor': line.numero_contenedor or '',
                'purchase_line_id': line.id,
                'origin': f"{self.name} - Línea {line.id}",
            })
            
            _logger.info("📋 DEBUG: Move vals para línea %s: %s", line.id, move_vals)
            res.append(move_vals)

        _logger.info("🏭 DEBUG: Total move_vals preparados: %s", len(res))
        return res

    def button_confirm(self):
        """
        Agregar logs al confirmar la orden
        """
        _logger.info("🔘 DEBUG: button_confirm llamado para orden %s", self.name)
        _logger.info("🔘 DEBUG: Estado actual: %s", self.state)
        
        result = super().button_confirm()
        
        _logger.info("🔘 DEBUG: Orden confirmada. Nuevo estado: %s", self.state)
        
        # Log de los pickings creados
        pickings = self.picking_ids
        _logger.info("🔘 DEBUG: Pickings creados: %s", len(pickings))
        
        for picking in pickings:
            _logger.info("📦 DEBUG: Picking %s - Moves: %s", picking.name, len(picking.move_ids_without_package))
            for move in picking.move_ids_without_package:
                _logger.info("📦 DEBUG: Move %s - Producto: %s, Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.product_id.name, move.marble_height, move.marble_width, 
                           move.marble_sqm, move.lot_general)
        
        return result
```

-e ### ./models/sale_order_line.py
```
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
```

-e ### ./models/sale_order.py
```
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_cancel(self):
        # Guardar procurement_group_id antes de cancelar
        procurement_groups = {
            order.id: order.procurement_group_id.id
            for order in self
            if order.procurement_group_id
        }
        # Cancelar los stock moves pendientes
        for order in self:
            moves = order.order_line.mapped('move_ids').filtered(
                lambda m: m.state not in ('done', 'cancel')
            )
            if moves:
                moves._action_cancel()
        # Cambiar estado a 'cancel' sin limpiar procurement_group_id
        result = self.write({'state': 'cancel'})
        # Restaurar procurement_group_id
        for order in self:
            saved = procurement_groups.get(order.id)
            if saved and (not order.procurement_group_id or order.procurement_group_id.id != saved):
                order.procurement_group_id = saved
        return result

    def action_draft(self):
        # Guardar procurement_group_id antes de pasar a borrador
        procurement_groups = {
            order.id: order.procurement_group_id.id
            for order in self
            if order.procurement_group_id
        }
        result = super().action_draft()
        # Restaurar procurement_group_id si se perdió
        for order in self:
            saved = procurement_groups.get(order.id)
            if saved and not order.procurement_group_id:
                order.procurement_group_id = saved
        return result

    def action_confirm(self):
        # Reutilizar procurement_group_id y PO existentes si aplica
        for order in self:
            if order.procurement_group_id:
                self.env['purchase.order'].search([
                    ('group_id', '=', order.procurement_group_id.id)
                ])
        return super().action_confirm()
```

-e ### ./models/stock_lot.py
```
from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²')
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    numero_contenedor = fields.Char('Número de Contenedor')
```

-e ### ./models/stock_move_line.py
```
# models/stock_move_line.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    numero_contenedor = fields.Char('Número de Contenedor')

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            line.marble_sqm = (line.marble_height or 0.0) * (line.marble_width or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        Lot = self.env['stock.lot']
        Seq = self.env['ir.sequence'].sudo()

        for vals in vals_list:
            # Solo para entradas sin lot_id pero con lot_general definido
            if vals.get('lot_general') and not vals.get('lot_id'):
                picking_code = vals.get('picking_code')
                if not picking_code and vals.get('move_id'):
                    move = self.env['stock.move'].browse(vals['move_id'])
                    picking_code = move.picking_type_id.code
                if picking_code == 'incoming':
                    lot_general = vals['lot_general']
                    seq_code = f"marble.serial.{lot_general}"
                    sequence = Seq.search([('code', '=', seq_code)], limit=1)
                    if not sequence:
                        sequence = Seq.create({
                            'name': _('Secuencia Mármol %s') % lot_general,
                            'code': seq_code,
                            'padding': 3,
                            'prefix': f"{lot_general}-",
                        })
                    lot_name = sequence.next_by_id()
                    new_lot = Lot.create({
                        'name': lot_name,
                        'product_id': vals.get('product_id'),
                        'company_id': vals.get('company_id'),
                        'marble_height': vals.get('marble_height'),
                        'marble_width': vals.get('marble_width'),
                        'numero_contenedor': vals.get('numero_contenedor', ''),
                        'marble_sqm': (vals.get('marble_height') or 0.0) * (vals.get('marble_width') or 0.0),
                        'lot_general': lot_general,
                        'marble_thickness': vals.get('marble_thickness', 0.0),
                    })
                    vals['lot_id'] = new_lot.id

        return super().create(vals_list)

    def write(self, vals):
        if 'lot_general' not in vals or not vals['lot_general']:
            return super().write(vals)

        Lot = self.env['stock.lot']
        Seq = self.env['ir.sequence'].sudo()
        to_process = self.filtered(lambda l: not l.lot_id and l.picking_id.picking_type_id.code == 'incoming')

        for line in to_process:
            lot_general = vals['lot_general']
            seq_code = f"marble.serial.{lot_general}"
            sequence = Seq.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = Seq.create({
                    'name': _('Secuencia Mármol %s') % lot_general,
                    'code': seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })
            lot_name = sequence.next_by_id()
            new_lot = Lot.create({
                'name': lot_name,
                'product_id': vals.get('product_id', line.product_id.id),
                'company_id': line.company_id.id,
                'marble_height': vals.get('marble_height', line.marble_height),
                'marble_width': vals.get('marble_width', line.marble_width),
                'marble_sqm': (vals.get('marble_height', line.marble_height) or 0.0) * (vals.get('marble_width', line.marble_width) or 0.0),
                'lot_general': lot_general,
                'marble_thickness': vals.get('marble_thickness', line.marble_thickness),
                'numero_contenedor': vals.get('numero_contenedor', line.numero_contenedor),
            })
            update_vals = vals.copy()
            update_vals['lot_id'] = new_lot.id
            super(StockMoveLine, line).write(update_vals)

        with_lot = self.filtered(lambda l: l.lot_id)
        if with_lot:
            super(StockMoveLine, with_lot).write(vals)

        return True

    @api.onchange('lot_general')
    def _onchange_lot_general(self):
        if self.lot_general and not self.lot_id:
            return {
                'warning': {
                    'title': _('Información'),
                    'message': _('Al guardar, se generará un número de serie automático.')
                }
            }
```

-e ### ./models/stock_move.py
```
# models/stock_move.py

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")
    lot_id = fields.Many2one('stock.lot', string='Número de Serie (Venta)')
    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    is_outgoing = fields.Boolean(string='Es Salida', compute='_compute_is_outgoing', store=True)
    pedimento_number = fields.Char(string='Número de Pedimento', size=18)
    numero_contenedor = fields.Char('Número de Contenedor')

    lot_selection_mode = fields.Selection([
        ('existing', 'Seleccionar Lote Existente'),
        ('manual', 'Crear Nuevo Lote')
    ], string='Modo de Lote', default='manual')
    existing_lot_id = fields.Many2one(
        'stock.lot',
        string='Lote Existente',
        domain="[('product_id','=',product_id),('id','in',available_lot_ids)]"
    )
    available_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_available_lots',
        string='Lotes Disponibles'
    )

    @api.depends('product_id')
    def _compute_available_lots(self):
        for move in self:
            if move.product_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                    ('lot_id', '!=', False),
                ])
                move.available_lot_ids = quants.mapped('lot_id')
            else:
                move.available_lot_ids = False

    @api.onchange('lot_selection_mode')
    def _onchange_lot_selection_mode(self):
        if self.lot_selection_mode == 'existing':
            self.lot_general = False
            self.marble_height = 0.0
            self.marble_width = 0.0
            self.marble_thickness = 0.0
            self.pedimento_number = False
        else:
            self.existing_lot_id = False

    @api.onchange('existing_lot_id')
    def _onchange_existing_lot_id(self):
        """
        Al seleccionar un lote existente, este onchange hace dos cosas:
        1. Actualiza los datos de la línea actual.
        2. Ajusta otras líneas del mismo albarán si están desincronizadas.
        """
        if self.lot_selection_mode == 'existing' and self.existing_lot_id:
            lot = self.existing_lot_id

            # 1. Actualiza la línea actual
            self.lot_general = lot.lot_general
            self.marble_height = lot.marble_height
            self.marble_width = lot.marble_width
            self.marble_sqm = lot.marble_sqm
            self.marble_thickness = lot.marble_thickness
            self.lot_id = lot.id
            self.so_lot_id = lot.id
            self.numero_contenedor = lot.numero_contenedor

            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], limit=1, order='in_date DESC')
            self.pedimento_number = quant.pedimento_number or ''

            # 2. Sincroniza otras líneas del mismo picking
            if self.picking_id:
                for other_move in self.picking_id.move_ids_without_package:
                    if other_move == self._origin:
                        continue
                    if other_move.lot_id and other_move.marble_sqm != other_move.lot_id.marble_sqm:
                        other_quant = self.env['stock.quant'].search([
                            ('lot_id', '=', other_move.lot_id.id),
                            ('quantity', '>', 0),
                            ('location_id.usage', '=', 'internal'),
                        ], limit=1, order='in_date DESC')
                        other_move.lot_general = other_move.lot_id.lot_general
                        other_move.marble_height = other_move.lot_id.marble_height
                        other_move.marble_width = other_move.lot_id.marble_width
                        other_move.marble_sqm = other_move.lot_id.marble_sqm
                        other_move.marble_thickness = other_move.lot_id.marble_thickness
                        other_move.pedimento_number = other_quant.pedimento_number or ''

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for move in self:
            move.marble_sqm = (move.marble_height or 0.0) * (move.marble_width or 0.0)

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = (move.picking_type_id.code == 'outgoing')

    @api.model_create_multi
    def create(self, vals_list):
        """
        Agregar logs al crear stock moves
        """
        _logger.info("🆕 DEBUG: StockMove.create llamado con %s moves", len(vals_list))
        
        for i, vals in enumerate(vals_list):
            _logger.info("🆕 DEBUG: Move %s - Producto ID: %s, Nombre: %s", 
                        i, vals.get('product_id'), vals.get('name'))
            _logger.info("🆕 DEBUG: Move %s - Altura: %s, Ancho: %s, m²: %s, Lote: %s, PO Line: %s", 
                        i, vals.get('marble_height'), vals.get('marble_width'), 
                        vals.get('marble_sqm'), vals.get('lot_general'), vals.get('purchase_line_id'))
        
        moves = super().create(vals_list)
        
        _logger.info("🆕 DEBUG: Moves creados - Total: %s", len(moves))
        for move in moves:
            _logger.info("🆕 DEBUG: Move creado ID: %s - Producto: %s, Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        move.id, move.product_id.name, move.marble_height, move.marble_width, 
                        move.marble_sqm, move.lot_general)
        
        return moves

    def write(self, vals):
        """
        Agregar logs al escribir stock moves
        """
        if vals:
            _logger.info("✏️ DEBUG: StockMove.write llamado para %s moves", len(self))
            _logger.info("✏️ DEBUG: Valores a escribir: %s", vals)
            
            for move in self:
                _logger.info("✏️ DEBUG: Move %s - Antes: Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
        
        # El write se centra en su funcionalidad principal.
        result = super().write(vals)
        
        if vals and any(key.startswith('marble_') or key == 'lot_general' for key in vals.keys()):
            for move in self:
                _logger.info("✏️ DEBUG: Move %s - Después: Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
        
        if self:
            self._propagate_marble_data_to_move_lines()
        return result

    def _propagate_marble_data_to_move_lines(self):
        """
        Propaga los datos de mármol y lote a las líneas de movimiento asociadas.
        """
        for move in self:
            if not move.exists():
                continue
            if move.move_line_ids:
                data = {
                    'marble_height': move.marble_height,
                    'marble_width': move.marble_width,
                    'marble_sqm': move.marble_sqm,
                    'lot_general': move.lot_general,
                    'marble_thickness': move.marble_thickness,
                    'pedimento_number': move.pedimento_number or '',
                    'numero_contenedor': move.numero_contenedor,
                }
                if move.lot_id:
                    data['lot_id'] = move.lot_id.id
                move.move_line_ids.write(data)

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)
        marble_data = {
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'pedimento_number': self.pedimento_number or '',
            'numero_contenedor': self.numero_contenedor or '',
        }
        if self.is_outgoing and self.lot_id:
            marble_data['lot_id'] = self.lot_id.id
        vals.update(marble_data)
        return vals

    def _action_assign(self):
        result = super()._action_assign()
        for move in self:
            if move.move_line_ids and (move.lot_id or move.marble_sqm or move.lot_general):
                move._propagate_marble_data_to_move_lines()
        return result

    def _action_done(self, cancel_backorder=False):
        for move in self:
            move._propagate_marble_data_to_move_lines()
        return super()._action_done(cancel_backorder=cancel_backorder)

    # ===== MÉTODOS PARA PREVENIR AGRUPACIÓN =====

    def _search_picking_for_assignation(self):
        """
        Sobrescribir para evitar que se agrupen moves con diferentes datos de mármol
        """
        result = super()._search_picking_for_assignation()
        return result

    def _key_assign_picking(self):
        """
        Sobrescribir la clave de agrupación para incluir datos de mármol
        """
        key = super()._key_assign_picking()
        # Añadir datos de mármol a la clave para evitar agrupación incorrecta
        marble_key = (
            self.marble_height or 0.0,
            self.marble_width or 0.0, 
            self.marble_sqm or 0.0,
            self.lot_general or '',
            self.marble_thickness or 0.0,
            self.numero_contenedor or '',
            self.purchase_line_id.id if self.purchase_line_id else 0,
        )
        
        final_key = key + marble_key
        _logger.info("🔑 DEBUG: _key_assign_picking para move %s - Clave: %s", self.id, final_key)
        return final_key

    @api.model 
    def _prepare_merge_moves_distinct_fields(self):
        """
        Especificar qué campos deben ser distintos para evitar merge
        """
        distinct_fields = super()._prepare_merge_moves_distinct_fields()
        # Añadir campos de mármol que deben mantenerse distintos
        marble_fields = [
            'marble_height', 'marble_width', 'marble_sqm', 
            'lot_general', 'marble_thickness', 'numero_contenedor',
            'purchase_line_id'
        ]
        distinct_fields.extend(marble_fields)
        return distinct_fields

    def _merge_moves_fields(self):
        """
        Sobrescribir para evitar que se fusionen moves con diferentes datos de mármol
        """
        result = super()._merge_moves_fields()
        # Añadir campos de mármol que no deben fusionarse
        marble_fields = {
            'marble_height', 'marble_width', 'marble_sqm',
            'lot_general', 'marble_thickness', 'numero_contenedor'
        }
        # Eliminar campos de mármol de los campos que se pueden fusionar
        for field in marble_fields:
            if field in result:
                result.pop(field)
        return result

    def _should_be_assigned(self):
        """
        Sobrescribir para considerar los datos de mármol en la asignación
        """
        result = super()._should_be_assigned()
        # Si tiene datos de mármol específicos, debe ser asignado individualmente
        if self.marble_sqm > 0 or self.lot_general:
            return True
        return result

    def _merge_moves(self, merge_into=False):
        """
        Prevenir merge de moves con diferentes características de mármol
        """
        _logger.info("🔄 DEBUG: _merge_moves llamado para %s moves", len(self))
        
        # Agrupar moves por sus características de mármol
        marble_groups = {}
        for move in self:
            marble_key = (
                move.marble_height or 0.0,
                move.marble_width or 0.0,
                move.marble_sqm or 0.0,
                move.lot_general or '',
                move.marble_thickness or 0.0,
                move.numero_contenedor or '',
                move.purchase_line_id.id if move.purchase_line_id else 0,
            )
            if marble_key not in marble_groups:
                marble_groups[marble_key] = self.env['stock.move']
            marble_groups[marble_key] |= move
            
            _logger.info("🔄 DEBUG: Move %s agrupado con clave: %s", move.id, marble_key)

        _logger.info("🔄 DEBUG: Grupos de mármol creados: %s", len(marble_groups))

        # Solo hacer merge dentro de cada grupo con las mismas características
        merged_moves = self.env['stock.move']
        for i, (marble_key, group_moves) in enumerate(marble_groups.items()):
            _logger.info("🔄 DEBUG: Procesando grupo %s con %s moves", i, len(group_moves))
            
            if len(group_moves) > 1:
                _logger.info("🔄 DEBUG: Haciendo merge de grupo %s", i)
                merged_moves |= super(StockMove, group_moves)._merge_moves(merge_into)
            else:
                _logger.info("🔄 DEBUG: Grupo %s no necesita merge", i)
                merged_moves |= group_moves

        _logger.info("🔄 DEBUG: Moves después del merge: %s", len(merged_moves))
        return merged_moves
```

-e ### ./models/stock_picking.py
```
# models/stock_picking.py

from odoo import models, api, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _sync_moves_with_lots(self):
        """
        Función clave para asegurar la coherencia de datos.
        Itera sobre todos los movimientos y fuerza que sus datos de mármol
        reflejen los del lote que tienen asignado.
        Esto previene la propagación de datos incorrectos (ej. dimensiones cero).
        """
        for move in self.move_ids_without_package:
            # Condición 1: El movimiento tiene un lote asignado.
            # Condición 2: Los m² del movimiento no coinciden con los m² del lote
            # o el pedimento no coincide (indicador de desincronización).
            if move.lot_id and (
                move.marble_sqm != move.lot_id.marble_sqm or
                (hasattr(move, 'pedimento_number') and hasattr(move.lot_id, 'pedimento_number') and move.pedimento_number != move.lot_id.pedimento_number)
            ):
                # Se obtienen los datos del quant para el número de pedimento
                quant = self.env['stock.quant'].search([
                    ('lot_id', '=', move.lot_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                ], limit=1, order='in_date DESC')

                # Actualizar el movimiento para que refleje los datos correctos de su lote.
                move.with_context(skip_sync=True).write({
                    'marble_height':    move.lot_id.marble_height,
                    'marble_width':     move.lot_id.marble_width,
                    'marble_sqm':       move.lot_id.marble_sqm,
                    'lot_general':      move.lot_id.lot_general,
                    'marble_thickness': move.lot_id.marble_thickness,
                    'pedimento_number': quant.pedimento_number or '',
                    'numero_contenedor': move.lot_id.numero_contenedor,

                })

    def write(self, vals):
        """
        Sobrescribimos write para ejecutar la sincronización al guardar.
        Esto mejora la experiencia de usuario, evitando "reseteos" visuales.
        """
        # Primero, ejecutar el write original
        res = super().write(vals)
        # Después de cualquier escritura, ejecutar la sincronización.
        # Esto es especialmente útil después de añadir nuevas líneas.
        if self.state not in ('done', 'cancel'):
            for picking in self:
                picking._sync_moves_with_lots()
        return res

    def button_validate(self):
        # --- PASO 1: Sincronización Forzada y Preventiva ---
        self._sync_moves_with_lots()
        
        # --- PASO 2: Sincronización opcional desde la Venta (si el move está vacío) ---
        if self.picking_type_id.code == 'outgoing':
            for move in self.move_ids_without_package:
                if move.sale_line_id and not move.lot_id and not move.marble_sqm > 0:
                    sale = move.sale_line_id
                    if sale.marble_sqm > 0 or sale.lot_id:
                        move.write({
                            'marble_height':    sale.marble_height,
                            'marble_width':     sale.marble_width,
                            'marble_sqm':       sale.marble_sqm,
                            'lot_general':      sale.lot_general,
                            'marble_thickness': sale.marble_thickness,
                            'pedimento_number': sale.pedimento_number,
                            'lot_id':           sale.lot_id.id,
                            'numero_contenedor': sale.numero_contenedor,
                        })

        # --- PASO 3: Propagación Final a las Líneas de Operación ---
        for move in self.move_ids_without_package:
            if move.lot_id or move.marble_sqm > 0:
                move._propagate_marble_data_to_move_lines()

        result = super().button_validate()
        return result

    def _action_done(self):
        # Como red de seguridad final, volvemos a sincronizar y corregir.
        for line in self.move_line_ids.filtered(lambda l: l.lot_id and l.quantity > 0):
            lot = line.lot_id
            
            expected_data = {
                'marble_height': lot.marble_height,
                'marble_width': lot.marble_width,
                'marble_sqm': lot.marble_sqm,
                'lot_general': lot.lot_general,
                'marble_thickness': lot.marble_thickness,
                'numero_contenedor': lot.numero_contenedor,
            }
            
            # Buscamos el pedimento del quant correspondiente
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id), ('quantity', '>', 0), ('location_id.usage', '=', 'internal'),
            ], limit=1, order='in_date DESC')
            if quant:
                expected_data['pedimento_number'] = quant.pedimento_number or ''

            # Creamos un diccionario con los datos a verificar/actualizar
            data_to_write = {}
            for field, value in expected_data.items():
                if getattr(line, field) != value:
                    data_to_write[field] = value

            if data_to_write:
                line.write(data_to_write)
        
        result = super()._action_done()
        return result
```

-e ### ./models/stock_quant.py
```
from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    marble_height = fields.Float('Altura (m)', related='lot_id.marble_height', store=True)
    marble_width = fields.Float('Ancho (m)', related='lot_id.marble_width', store=True)
    marble_sqm = fields.Float('m²', related='lot_id.marble_sqm', store=True)
    lot_general = fields.Char('Lote', related='lot_id.lot_general', store=True)
    marble_thickness = fields.Float('Grosor (cm)', related='lot_id.marble_thickness', store=True)
    numero_contenedor = fields.Char('Número de Contenedor', related='lot_id.numero_contenedor', store=True)
```

-e ### ./models/stock_rule.py
```
# models/stock_rule.py

from odoo import models

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom,
            location_id, name, origin, company_id, values
        )

        sale_line_id = values.get('sale_line_id')
        if sale_line_id:
            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            if sale_line.exists():
                marble_data = {
                    'marble_height':    sale_line.marble_height,
                    'marble_width':     sale_line.marble_width,
                    'marble_sqm':       sale_line.marble_sqm,
                    'lot_general':      sale_line.lot_general,
                    'pedimento_number': sale_line.pedimento_number,
                    'marble_thickness': sale_line.marble_thickness,
                    'numero_contenedor': sale_line.numero_contenedor,
                }
                if sale_line.lot_id:
                    marble_data.update({
                        'so_lot_id': sale_line.lot_id.id,
                        'lot_id':    sale_line.lot_id.id,
                    })
                res.update(marble_data)
        else:
            marble_data = {
                'marble_height':    values.get('marble_height', 0.0),
                'marble_width':     values.get('marble_width', 0.0),
                'marble_sqm':       values.get('marble_sqm', 0.0),
                'lot_general':      values.get('lot_general', ''),
                'pedimento_number': values.get('pedimento_number', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
                'numero_contenedor': values.get('numero_contenedor', ''),
            }
            forced_lot = values.get('lot_id')
            if forced_lot:
                marble_data.update({
                    'so_lot_id': forced_lot,
                    'lot_id':    forced_lot,
                })
            res.update(marble_data)

        return res
```

-e ### ./salida_modulo_completo.md
```
-e ### ./data/ir_sequence_data.xml
```
<odoo noupdate="1">
</odoo>
```

-e ### ./models/procurement_group.py
```
from odoo import models, api

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _run_buy(self, procurements):  # procurements es una lista de tuplas (procurement_request, rule)
        procurement_data_to_apply = {}  # {proc_key: marble_data_dict}
        # Nuevo: mapeo de proc_key a los valores originales del procurement_request para _prepare_purchase_order_line
        original_proc_values_map = {}

        # BUCLE 1: Extraer y almacenar los datos de mármol
        for procurement_request, rule in procurements:
            if not hasattr(procurement_request, 'product_id') or \
               not hasattr(procurement_request, 'origin') or \
               not hasattr(procurement_request, 'values'):
                continue

            product_record = procurement_request.product_id
            origin_str = procurement_request.origin  # Este es el SO (ej. S00002)

            # procurement_request.values es el diccionario de valores que llega a _run_buy.
            current_proc_values = procurement_request.values or {}

            proc_key = f"{product_record.id}_{origin_str}"
            original_proc_values_map[proc_key] = current_proc_values  # Guardamos los valores que SÍ llegan

            marble_data_found = {}

            # Intento 1: ¿Están los campos de mármol directamente en current_proc_values?
            if 'marble_sqm' in current_proc_values and current_proc_values.get('marble_sqm', 0.0) > 0:
                marble_data_found = {
                    'marble_height': current_proc_values.get('marble_height', 0.0),
                    'marble_width': current_proc_values.get('marble_width', 0.0),
                    'marble_sqm': current_proc_values.get('marble_sqm', 0.0),
                    'lot_general': current_proc_values.get('lot_general', ''),
                    'marble_thickness': current_proc_values.get('marble_thickness', 0.0),
                    'numero_contenedor': current_proc_values.get('numero_contenedor', ''),
                }

            # Intento 2: Si no, intentar obtenerlos del stock.move de origen (move_dest_ids)
            if not marble_data_found and 'move_dest_ids' in current_proc_values and current_proc_values['move_dest_ids']:
                source_moves = current_proc_values['move_dest_ids']
                if isinstance(source_moves, models.BaseModel) and source_moves._name == 'stock.move':
                    first_move = source_moves[0] if source_moves else None
                    if first_move and first_move.marble_sqm > 0:  # Chequeamos si el move tiene los m2
                        marble_data_found = {
                            'marble_height': first_move.marble_height,
                            'marble_width': first_move.marble_width,
                            'marble_sqm': first_move.marble_sqm,
                            'lot_general': first_move.lot_general,
                            'marble_thickness': first_move.marble_thickness,
                            'numero_contenedor': first_move.numero_contenedor,
                            
                        }
                        # IMPORTANTE: Añadir estos datos al diccionario original_proc_values_map[proc_key]
                        original_proc_values_map[proc_key].update(marble_data_found)

            if marble_data_found:
                procurement_data_to_apply[proc_key] = marble_data_found

        # Pasar el mapa de valores originales al contexto para que _prepare_purchase_order_line lo use
        self_with_context = self.with_context(original_proc_values_map=original_proc_values_map)

        res = super(StockRule, self_with_context)._run_buy(procurements)  # Llamar a super con el contexto modificado

        # BUCLE 2: Aplicar/Reafirmar los datos de mármol a las PO Lines.
        if procurement_data_to_apply:
            for procurement_request, rule in procurements:
                if not hasattr(procurement_request, 'product_id') or not hasattr(procurement_request, 'origin'):
                    continue
                product_record = procurement_request.product_id
                origin_str = procurement_request.origin
                proc_key = f"{product_record.id}_{origin_str}"

                if proc_key in procurement_data_to_apply:
                    marble_data = procurement_data_to_apply[proc_key]
                    current_proc_values = procurement_request.values or {}
                    move_dest_ids_val = current_proc_values.get('move_dest_ids')

                    if move_dest_ids_val:
                        actual_move_ids = []
                        # Asegurarse de que move_dest_ids_val es un iterable de IDs
                        if isinstance(move_dest_ids_val, models.BaseModel):  # Si es un recordset
                            actual_move_ids = move_dest_ids_val.ids
                        elif isinstance(move_dest_ids_val, (list, tuple)) and all(isinstance(i, int) for i in move_dest_ids_val):  # Si es una lista/tupla de IDs
                            actual_move_ids = list(move_dest_ids_val)
                        elif isinstance(move_dest_ids_val, int):  # Si es un solo ID
                            actual_move_ids = [move_dest_ids_val]

                        if not actual_move_ids:
                            continue

                        po_lines = self.env['purchase.order.line'].search([
                            ('move_dest_ids', 'in', actual_move_ids)
                        ])

                        if po_lines:
                            for po_line in po_lines:
                                po_line.with_context(from_procurement=True).write(marble_data)
        return res

    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        origin_str = values.get('origin')  # El origin del procurement_request
        proc_key = f"{product_id.id}_{origin_str}"

        original_proc_values_map = self.env.context.get('original_proc_values_map', {})
        # Usar los valores enriquecidos del mapa si existen para esta clave, sino los 'values' directos.
        values_for_po_line = original_proc_values_map.get(proc_key, values)

        # Llamar a super con los 'values' originales.
        res_vals = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)

        marble_fields_to_set = {}
        # Ahora usamos 'values_for_po_line' que debería tener los datos de mármol.
        if values_for_po_line.get('marble_sqm', 0.0) > 0:  # Condición principal para aplicar datos de mármol
            marble_fields_to_set['marble_sqm'] = values_for_po_line.get('marble_sqm', 0.0)
            marble_fields_to_set['marble_height'] = values_for_po_line.get('marble_height', 0.0)
            marble_fields_to_set['marble_width'] = values_for_po_line.get('marble_width', 0.0)
            marble_fields_to_set['lot_general'] = values_for_po_line.get('lot_general', '')
            marble_fields_to_set['marble_thickness'] = values_for_po_line.get('marble_thickness', 0.0)
            marble_fields_to_set['numero_contenedor'] = values_for_po_line.get('numero_contenedor', '')
        if marble_fields_to_set:
            res_vals.update(marble_fields_to_set)

        return res_vals
```

-e ### ./models/product_template.py
```
# models/product_template.py
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Precios por metro cuadrado
    price_per_sqm_min = fields.Float(
        string='Precio Mínimo por m²',
        digits='Product Price',
        help='Precio mínimo de venta por metro cuadrado'
    )
    
    price_per_sqm_avg = fields.Float(
        string='Precio Promedio por m²',
        digits='Product Price',
        help='Precio promedio de venta por metro cuadrado'
    )
    
    price_per_sqm_max = fields.Float(
        string='Precio Máximo por m²',
        digits='Product Price',
        help='Precio máximo de venta por metro cuadrado'
    )

    # --- INICIO DEL CAMBIO ---
    # Añade este nuevo campo
    require_lot_selection_on_sale = fields.Boolean(
        string="Exigir Lote Específico en Venta",
        default=True,
        help="Si se marca, será obligatorio seleccionar un número de lote/serie en la orden de venta si hay stock disponible.
"
             "Desmarcar para productos (como porcelanato) donde el lote se puede asignar durante el picking en el almacén."
    )
    # --- FIN DEL CAMBIO ---
```

-e ### ./models/purchase_order_line.py
```
# models/purchase_order_line.py

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    marble_height = fields.Float('Altura (m)', store=True)
    marble_width = fields.Float('Ancho (m)', store=True)
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote', store=True)
    marble_thickness = fields.Float('Grosor (cm)')
    numero_contenedor = fields.Char('Número de Contenedor', store=True)

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        """
        Lógica de cálculo HÍBRIDA:
        - Si se especifican altura y ancho, calcula los m².
        - Si NO se especifican, NO HACE NADA, permitiendo que el valor
          introducido manualmente por el usuario se conserve.
        """
        for line in self:
            if line.marble_height > 0 and line.marble_width > 0:
                line.marble_sqm = line.marble_height * line.marble_width

    @api.onchange('marble_height', 'marble_width', 'lot_general')
    def _onchange_marble_fields(self):
        return

    def write(self, vals):
        res = super().write(vals)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        return lines

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        self.ensure_one()
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        
        _logger.info("🔍 DEBUG: _prepare_stock_move_vals para línea PO %s", self.id)
        _logger.info("🔍 DEBUG: Producto: %s, Cantidad: %s", self.product_id.name, product_uom_qty)
        _logger.info("🔍 DEBUG: Datos mármol - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                    self.marble_height, self.marble_width, self.marble_sqm, self.lot_general)
        
        # CLAVE: Añadir un identificador único para evitar agrupación
        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'numero_contenedor': self.numero_contenedor or '',
            # Añadir referencia única a la línea de compra para evitar agrupación
            'purchase_line_id': self.id,
            'origin': f"{self.order_id.name} - Línea {self.id}",
        })
        
        _logger.info("🔍 DEBUG: Stock move vals preparados: %s", vals)
        return vals

    def _create_stock_moves(self, picking):
        """
        Sobrescribir para asegurar que cada línea genera su propio move independiente
        """
        _logger.info("🚀 DEBUG: _create_stock_moves llamado para %s líneas", len(self))
        
        moves = self.env['stock.move']
        
        for line in self:
            _logger.info("🔄 DEBUG: Procesando línea PO %s - Producto: %s", line.id, line.product_id.name)
            _logger.info("🔄 DEBUG: Datos línea - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        line.marble_height, line.marble_width, line.marble_sqm, line.lot_general)
            
            # Crear un move individual para cada línea
            move_vals = line._prepare_stock_move_vals(
                picking, 
                line.price_unit, 
                line.product_qty, 
                line.product_uom
            )
            
            # Asegurar que el move tenga un nombre único
            move_vals['name'] = f"{line.order_id.name} - {line.product_id.name} - Línea {line.id}"
            
            _logger.info("🔄 DEBUG: Creando move con vals: %s", move_vals)
            
            move = self.env['stock.move'].create(move_vals)
            moves |= move
            
            _logger.info("✅ DEBUG: Move creado ID: %s - Nombre: %s", move.id, move.name)
            _logger.info("✅ DEBUG: Move datos - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
            
        _logger.info("🏁 DEBUG: Total moves creados: %s", len(moves))
        return moves

    def _get_stock_move_map(self):
        """
        Sobrescribir para evitar que Odoo agrupe movimientos por producto
        """
        _logger.info("🗺️ DEBUG: _get_stock_move_map llamado para %s líneas", len(self))
        
        # En lugar de agrupar por producto, crear un mapeo único por línea
        move_map = {}
        for line in self:
            # Usar el ID de la línea como clave única
            key = f"line_{line.id}_{line.product_id.id}"
            move_map[key] = {
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'lines': [line],
            }
            _logger.info("🗺️ DEBUG: Mapeando línea %s con clave única: %s", line.id, key)
        
        _logger.info("🗺️ DEBUG: Move map final: %s", move_map)
        return move_map
```

-e ### ./models/purchase_order.py
```
# models/purchase_order.py

from odoo import models
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _prepare_stock_moves(self, picking):
        """
        Sobrescribir para asegurar que cada línea de PO genere su propio move
        """
        self.ensure_one()
        _logger.info("🏭 DEBUG: PurchaseOrder._prepare_stock_moves para orden %s", self.name)
        _logger.info("🏭 DEBUG: Número de líneas en la orden: %s", len(self.order_line))
        
        res = []

        for line in self.order_line:
            _logger.info("📋 DEBUG: Procesando línea orden %s - Producto: %s", line.id, line.product_id.name)
            
            # Crear un move individual para cada línea
            move_vals = line._prepare_stock_move_vals(
                picking, 
                line.price_unit, 
                line.product_qty, 
                line.product_uom
            )
            
            # Asegurar nombre único y datos de mármol
            altura = line.marble_height or 0.0
            ancho = line.marble_width or 0.0
            marble_sqm = line.marble_sqm

            # Recalcula o ajusta marble_sqm según dimensiones
            if altura > 0 and ancho > 0:
                marble_sqm = altura * ancho
            elif not marble_sqm:
                marble_sqm = 0.0

            move_vals.update({
                'name': f"{self.name} - {line.product_id.name} [Línea {line.id}]",
                'marble_height': altura,
                'marble_width': ancho,
                'marble_sqm': marble_sqm,
                'marble_thickness': line.marble_thickness or 0.0,
                'lot_general': line.lot_general or '',
                'numero_contenedor': line.numero_contenedor or '',
                'purchase_line_id': line.id,
                'origin': f"{self.name} - Línea {line.id}",
            })
            
            _logger.info("📋 DEBUG: Move vals para línea %s: %s", line.id, move_vals)
            res.append(move_vals)

        _logger.info("🏭 DEBUG: Total move_vals preparados: %s", len(res))
        return res

    def button_confirm(self):
        """
        Agregar logs al confirmar la orden
        """
        _logger.info("🔘 DEBUG: button_confirm llamado para orden %s", self.name)
        _logger.info("🔘 DEBUG: Estado actual: %s", self.state)
        
        result = super().button_confirm()
        
        _logger.info("🔘 DEBUG: Orden confirmada. Nuevo estado: %s", self.state)
        
        # Log de los pickings creados
        pickings = self.picking_ids
        _logger.info("🔘 DEBUG: Pickings creados: %s", len(pickings))
        
        for picking in pickings:
            _logger.info("📦 DEBUG: Picking %s - Moves: %s", picking.name, len(picking.move_ids_without_package))
            for move in picking.move_ids_without_package:
                _logger.info("📦 DEBUG: Move %s - Producto: %s, Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.product_id.name, move.marble_height, move.marble_width, 
                           move.marble_sqm, move.lot_general)
        
        return result
```

-e ### ./models/sale_order_line.py
```
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
```

-e ### ./models/sale_order.py
```
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_cancel(self):
        # Guardar procurement_group_id antes de cancelar
        procurement_groups = {
            order.id: order.procurement_group_id.id
            for order in self
            if order.procurement_group_id
        }
        # Cancelar los stock moves pendientes
        for order in self:
            moves = order.order_line.mapped('move_ids').filtered(
                lambda m: m.state not in ('done', 'cancel')
            )
            if moves:
                moves._action_cancel()
        # Cambiar estado a 'cancel' sin limpiar procurement_group_id
        result = self.write({'state': 'cancel'})
        # Restaurar procurement_group_id
        for order in self:
            saved = procurement_groups.get(order.id)
            if saved and (not order.procurement_group_id or order.procurement_group_id.id != saved):
                order.procurement_group_id = saved
        return result

    def action_draft(self):
        # Guardar procurement_group_id antes de pasar a borrador
        procurement_groups = {
            order.id: order.procurement_group_id.id
            for order in self
            if order.procurement_group_id
        }
        result = super().action_draft()
        # Restaurar procurement_group_id si se perdió
        for order in self:
            saved = procurement_groups.get(order.id)
            if saved and not order.procurement_group_id:
                order.procurement_group_id = saved
        return result

    def action_confirm(self):
        # Reutilizar procurement_group_id y PO existentes si aplica
        for order in self:
            if order.procurement_group_id:
                self.env['purchase.order'].search([
                    ('group_id', '=', order.procurement_group_id.id)
                ])
        return super().action_confirm()
```

-e ### ./models/stock_lot.py
```
from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²')
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    numero_contenedor = fields.Char('Número de Contenedor')
```

-e ### ./models/stock_move_line.py
```
# models/stock_move_line.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    numero_contenedor = fields.Char('Número de Contenedor')

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            line.marble_sqm = (line.marble_height or 0.0) * (line.marble_width or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        Lot = self.env['stock.lot']
        Seq = self.env['ir.sequence'].sudo()

        for vals in vals_list:
            # Solo para entradas sin lot_id pero con lot_general definido
            if vals.get('lot_general') and not vals.get('lot_id'):
                picking_code = vals.get('picking_code')
                if not picking_code and vals.get('move_id'):
                    move = self.env['stock.move'].browse(vals['move_id'])
                    picking_code = move.picking_type_id.code
                if picking_code == 'incoming':
                    lot_general = vals['lot_general']
                    seq_code = f"marble.serial.{lot_general}"
                    sequence = Seq.search([('code', '=', seq_code)], limit=1)
                    if not sequence:
                        sequence = Seq.create({
                            'name': _('Secuencia Mármol %s') % lot_general,
                            'code': seq_code,
                            'padding': 3,
                            'prefix': f"{lot_general}-",
                        })
                    lot_name = sequence.next_by_id()
                    new_lot = Lot.create({
                        'name': lot_name,
                        'product_id': vals.get('product_id'),
                        'company_id': vals.get('company_id'),
                        'marble_height': vals.get('marble_height'),
                        'marble_width': vals.get('marble_width'),
                        'numero_contenedor': vals.get('numero_contenedor', ''),
                        'marble_sqm': (vals.get('marble_height') or 0.0) * (vals.get('marble_width') or 0.0),
                        'lot_general': lot_general,
                        'marble_thickness': vals.get('marble_thickness', 0.0),
                    })
                    vals['lot_id'] = new_lot.id

        return super().create(vals_list)

    def write(self, vals):
        if 'lot_general' not in vals or not vals['lot_general']:
            return super().write(vals)

        Lot = self.env['stock.lot']
        Seq = self.env['ir.sequence'].sudo()
        to_process = self.filtered(lambda l: not l.lot_id and l.picking_id.picking_type_id.code == 'incoming')

        for line in to_process:
            lot_general = vals['lot_general']
            seq_code = f"marble.serial.{lot_general}"
            sequence = Seq.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = Seq.create({
                    'name': _('Secuencia Mármol %s') % lot_general,
                    'code': seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })
            lot_name = sequence.next_by_id()
            new_lot = Lot.create({
                'name': lot_name,
                'product_id': vals.get('product_id', line.product_id.id),
                'company_id': line.company_id.id,
                'marble_height': vals.get('marble_height', line.marble_height),
                'marble_width': vals.get('marble_width', line.marble_width),
                'marble_sqm': (vals.get('marble_height', line.marble_height) or 0.0) * (vals.get('marble_width', line.marble_width) or 0.0),
                'lot_general': lot_general,
                'marble_thickness': vals.get('marble_thickness', line.marble_thickness),
                'numero_contenedor': vals.get('numero_contenedor', line.numero_contenedor),
            })
            update_vals = vals.copy()
            update_vals['lot_id'] = new_lot.id
            super(StockMoveLine, line).write(update_vals)

        with_lot = self.filtered(lambda l: l.lot_id)
        if with_lot:
            super(StockMoveLine, with_lot).write(vals)

        return True

    @api.onchange('lot_general')
    def _onchange_lot_general(self):
        if self.lot_general and not self.lot_id:
            return {
                'warning': {
                    'title': _('Información'),
                    'message': _('Al guardar, se generará un número de serie automático.')
                }
            }
```

-e ### ./models/stock_move.py
```
# models/stock_move.py

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")
    lot_id = fields.Many2one('stock.lot', string='Número de Serie (Venta)')
    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    is_outgoing = fields.Boolean(string='Es Salida', compute='_compute_is_outgoing', store=True)
    pedimento_number = fields.Char(string='Número de Pedimento', size=18)
    numero_contenedor = fields.Char('Número de Contenedor')

    lot_selection_mode = fields.Selection([
        ('existing', 'Seleccionar Lote Existente'),
        ('manual', 'Crear Nuevo Lote')
    ], string='Modo de Lote', default='manual')
    existing_lot_id = fields.Many2one(
        'stock.lot',
        string='Lote Existente',
        domain="[('product_id','=',product_id),('id','in',available_lot_ids)]"
    )
    available_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_available_lots',
        string='Lotes Disponibles'
    )

    @api.depends('product_id')
    def _compute_available_lots(self):
        for move in self:
            if move.product_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                    ('lot_id', '!=', False),
                ])
                move.available_lot_ids = quants.mapped('lot_id')
            else:
                move.available_lot_ids = False

    @api.onchange('lot_selection_mode')
    def _onchange_lot_selection_mode(self):
        if self.lot_selection_mode == 'existing':
            self.lot_general = False
            self.marble_height = 0.0
            self.marble_width = 0.0
            self.marble_thickness = 0.0
            self.pedimento_number = False
        else:
            self.existing_lot_id = False

    @api.onchange('existing_lot_id')
    def _onchange_existing_lot_id(self):
        """
        Al seleccionar un lote existente, este onchange hace dos cosas:
        1. Actualiza los datos de la línea actual.
        2. Ajusta otras líneas del mismo albarán si están desincronizadas.
        """
        if self.lot_selection_mode == 'existing' and self.existing_lot_id:
            lot = self.existing_lot_id

            # 1. Actualiza la línea actual
            self.lot_general = lot.lot_general
            self.marble_height = lot.marble_height
            self.marble_width = lot.marble_width
            self.marble_sqm = lot.marble_sqm
            self.marble_thickness = lot.marble_thickness
            self.lot_id = lot.id
            self.so_lot_id = lot.id
            self.numero_contenedor = lot.numero_contenedor

            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], limit=1, order='in_date DESC')
            self.pedimento_number = quant.pedimento_number or ''

            # 2. Sincroniza otras líneas del mismo picking
            if self.picking_id:
                for other_move in self.picking_id.move_ids_without_package:
                    if other_move == self._origin:
                        continue
                    if other_move.lot_id and other_move.marble_sqm != other_move.lot_id.marble_sqm:
                        other_quant = self.env['stock.quant'].search([
                            ('lot_id', '=', other_move.lot_id.id),
                            ('quantity', '>', 0),
                            ('location_id.usage', '=', 'internal'),
                        ], limit=1, order='in_date DESC')
                        other_move.lot_general = other_move.lot_id.lot_general
                        other_move.marble_height = other_move.lot_id.marble_height
                        other_move.marble_width = other_move.lot_id.marble_width
                        other_move.marble_sqm = other_move.lot_id.marble_sqm
                        other_move.marble_thickness = other_move.lot_id.marble_thickness
                        other_move.pedimento_number = other_quant.pedimento_number or ''

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for move in self:
            move.marble_sqm = (move.marble_height or 0.0) * (move.marble_width or 0.0)

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = (move.picking_type_id.code == 'outgoing')

    @api.model_create_multi
    def create(self, vals_list):
        """
        Agregar logs al crear stock moves
        """
        _logger.info("🆕 DEBUG: StockMove.create llamado con %s moves", len(vals_list))
        
        for i, vals in enumerate(vals_list):
            _logger.info("🆕 DEBUG: Move %s - Producto ID: %s, Nombre: %s", 
                        i, vals.get('product_id'), vals.get('name'))
            _logger.info("🆕 DEBUG: Move %s - Altura: %s, Ancho: %s, m²: %s, Lote: %s, PO Line: %s", 
                        i, vals.get('marble_height'), vals.get('marble_width'), 
                        vals.get('marble_sqm'), vals.get('lot_general'), vals.get('purchase_line_id'))
        
        moves = super().create(vals_list)
        
        _logger.info("🆕 DEBUG: Moves creados - Total: %s", len(moves))
        for move in moves:
            _logger.info("🆕 DEBUG: Move creado ID: %s - Producto: %s, Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        move.id, move.product_id.name, move.marble_height, move.marble_width, 
                        move.marble_sqm, move.lot_general)
        
        return moves

    def write(self, vals):
        """
        Agregar logs al escribir stock moves
        """
        if vals:
            _logger.info("✏️ DEBUG: StockMove.write llamado para %s moves", len(self))
            _logger.info("✏️ DEBUG: Valores a escribir: %s", vals)
            
            for move in self:
                _logger.info("✏️ DEBUG: Move %s - Antes: Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
        
        # El write se centra en su funcionalidad principal.
        result = super().write(vals)
        
        if vals and any(key.startswith('marble_') or key == 'lot_general' for key in vals.keys()):
            for move in self:
                _logger.info("✏️ DEBUG: Move %s - Después: Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
        
        if self:
            self._propagate_marble_data_to_move_lines()
        return result

    def _propagate_marble_data_to_move_lines(self):
        """
        Propaga los datos de mármol y lote a las líneas de movimiento asociadas.
        """
        for move in self:
            if not move.exists():
                continue
            if move.move_line_ids:
                data = {
                    'marble_height': move.marble_height,
                    'marble_width': move.marble_width,
                    'marble_sqm': move.marble_sqm,
                    'lot_general': move.lot_general,
                    'marble_thickness': move.marble_thickness,
                    'pedimento_number': move.pedimento_number or '',
                    'numero_contenedor': move.numero_contenedor,
                }
                if move.lot_id:
                    data['lot_id'] = move.lot_id.id
                move.move_line_ids.write(data)

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)
        marble_data = {
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'pedimento_number': self.pedimento_number or '',
            'numero_contenedor': self.numero_contenedor or '',
        }
        if self.is_outgoing and self.lot_id:
            marble_data['lot_id'] = self.lot_id.id
        vals.update(marble_data)
        return vals

    def _action_assign(self):
        result = super()._action_assign()
        for move in self:
            if move.move_line_ids and (move.lot_id or move.marble_sqm or move.lot_general):
                move._propagate_marble_data_to_move_lines()
        return result

    def _action_done(self, cancel_backorder=False):
        for move in self:
            move._propagate_marble_data_to_move_lines()
        return super()._action_done(cancel_backorder=cancel_backorder)

    # ===== MÉTODOS PARA PREVENIR AGRUPACIÓN =====

    def _search_picking_for_assignation(self):
        """
        Sobrescribir para evitar que se agrupen moves con diferentes datos de mármol
        """
        result = super()._search_picking_for_assignation()
        return result

    def _key_assign_picking(self):
        """
        Sobrescribir la clave de agrupación para incluir datos de mármol
        """
        key = super()._key_assign_picking()
        # Añadir datos de mármol a la clave para evitar agrupación incorrecta
        marble_key = (
            self.marble_height or 0.0,
            self.marble_width or 0.0, 
            self.marble_sqm or 0.0,
            self.lot_general or '',
            self.marble_thickness or 0.0,
            self.numero_contenedor or '',
            self.purchase_line_id.id if self.purchase_line_id else 0,
        )
        
        final_key = key + marble_key
        _logger.info("🔑 DEBUG: _key_assign_picking para move %s - Clave: %s", self.id, final_key)
        return final_key

    @api.model 
    def _prepare_merge_moves_distinct_fields(self):
        """
        Especificar qué campos deben ser distintos para evitar merge
        """
        distinct_fields = super()._prepare_merge_moves_distinct_fields()
        # Añadir campos de mármol que deben mantenerse distintos
        marble_fields = [
            'marble_height', 'marble_width', 'marble_sqm', 
            'lot_general', 'marble_thickness', 'numero_contenedor',
            'purchase_line_id'
        ]
        distinct_fields.extend(marble_fields)
        return distinct_fields

    def _merge_moves_fields(self):
        """
        Sobrescribir para evitar que se fusionen moves con diferentes datos de mármol
        """
        result = super()._merge_moves_fields()
        # Añadir campos de mármol que no deben fusionarse
        marble_fields = {
            'marble_height', 'marble_width', 'marble_sqm',
            'lot_general', 'marble_thickness', 'numero_contenedor'
        }
        # Eliminar campos de mármol de los campos que se pueden fusionar
        for field in marble_fields:
            if field in result:
                result.pop(field)
        return result

    def _should_be_assigned(self):
        """
        Sobrescribir para considerar los datos de mármol en la asignación
        """
        result = super()._should_be_assigned()
        # Si tiene datos de mármol específicos, debe ser asignado individualmente
        if self.marble_sqm > 0 or self.lot_general:
            return True
        return result

    def _merge_moves(self, merge_into=False):
        """
        Prevenir merge de moves con diferentes características de mármol
        """
        _logger.info("🔄 DEBUG: _merge_moves llamado para %s moves", len(self))
        
        # Agrupar moves por sus características de mármol
        marble_groups = {}
        for move in self:
            marble_key = (
                move.marble_height or 0.0,
                move.marble_width or 0.0,
                move.marble_sqm or 0.0,
                move.lot_general or '',
                move.marble_thickness or 0.0,
                move.numero_contenedor or '',
                move.purchase_line_id.id if move.purchase_line_id else 0,
            )
            if marble_key not in marble_groups:
                marble_groups[marble_key] = self.env['stock.move']
            marble_groups[marble_key] |= move
            
            _logger.info("🔄 DEBUG: Move %s agrupado con clave: %s", move.id, marble_key)

        _logger.info("🔄 DEBUG: Grupos de mármol creados: %s", len(marble_groups))

        # Solo hacer merge dentro de cada grupo con las mismas características
        merged_moves = self.env['stock.move']
        for i, (marble_key, group_moves) in enumerate(marble_groups.items()):
            _logger.info("🔄 DEBUG: Procesando grupo %s con %s moves", i, len(group_moves))
            
            if len(group_moves) > 1:
                _logger.info("🔄 DEBUG: Haciendo merge de grupo %s", i)
                merged_moves |= super(StockMove, group_moves)._merge_moves(merge_into)
            else:
                _logger.info("🔄 DEBUG: Grupo %s no necesita merge", i)
                merged_moves |= group_moves

        _logger.info("🔄 DEBUG: Moves después del merge: %s", len(merged_moves))
        return merged_moves
```

-e ### ./models/stock_picking.py
```
# models/stock_picking.py

from odoo import models, api, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _sync_moves_with_lots(self):
        """
        Función clave para asegurar la coherencia de datos.
        Itera sobre todos los movimientos y fuerza que sus datos de mármol
        reflejen los del lote que tienen asignado.
        Esto previene la propagación de datos incorrectos (ej. dimensiones cero).
        """
        for move in self.move_ids_without_package:
            # Condición 1: El movimiento tiene un lote asignado.
            # Condición 2: Los m² del movimiento no coinciden con los m² del lote
            # o el pedimento no coincide (indicador de desincronización).
            if move.lot_id and (
                move.marble_sqm != move.lot_id.marble_sqm or
                (hasattr(move, 'pedimento_number') and hasattr(move.lot_id, 'pedimento_number') and move.pedimento_number != move.lot_id.pedimento_number)
            ):
                # Se obtienen los datos del quant para el número de pedimento
                quant = self.env['stock.quant'].search([
                    ('lot_id', '=', move.lot_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                ], limit=1, order='in_date DESC')

                # Actualizar el movimiento para que refleje los datos correctos de su lote.
                move.with_context(skip_sync=True).write({
                    'marble_height':    move.lot_id.marble_height,
                    'marble_width':     move.lot_id.marble_width,
                    'marble_sqm':       move.lot_id.marble_sqm,
                    'lot_general':      move.lot_id.lot_general,
                    'marble_thickness': move.lot_id.marble_thickness,
                    'pedimento_number': quant.pedimento_number or '',
                    'numero_contenedor': move.lot_id.numero_contenedor,

                })

    def write(self, vals):
        """
        Sobrescribimos write para ejecutar la sincronización al guardar.
        Esto mejora la experiencia de usuario, evitando "reseteos" visuales.
        """
        # Primero, ejecutar el write original
        res = super().write(vals)
        # Después de cualquier escritura, ejecutar la sincronización.
        # Esto es especialmente útil después de añadir nuevas líneas.
        if self.state not in ('done', 'cancel'):
            for picking in self:
                picking._sync_moves_with_lots()
        return res

    def button_validate(self):
        # --- PASO 1: Sincronización Forzada y Preventiva ---
        self._sync_moves_with_lots()
        
        # --- PASO 2: Sincronización opcional desde la Venta (si el move está vacío) ---
        if self.picking_type_id.code == 'outgoing':
            for move in self.move_ids_without_package:
                if move.sale_line_id and not move.lot_id and not move.marble_sqm > 0:
                    sale = move.sale_line_id
                    if sale.marble_sqm > 0 or sale.lot_id:
                        move.write({
                            'marble_height':    sale.marble_height,
                            'marble_width':     sale.marble_width,
                            'marble_sqm':       sale.marble_sqm,
                            'lot_general':      sale.lot_general,
                            'marble_thickness': sale.marble_thickness,
                            'pedimento_number': sale.pedimento_number,
                            'lot_id':           sale.lot_id.id,
                            'numero_contenedor': sale.numero_contenedor,
                        })

        # --- PASO 3: Propagación Final a las Líneas de Operación ---
        for move in self.move_ids_without_package:
            if move.lot_id or move.marble_sqm > 0:
                move._propagate_marble_data_to_move_lines()

        result = super().button_validate()
        return result

    def _action_done(self):
        # Como red de seguridad final, volvemos a sincronizar y corregir.
        for line in self.move_line_ids.filtered(lambda l: l.lot_id and l.quantity > 0):
            lot = line.lot_id
            
            expected_data = {
                'marble_height': lot.marble_height,
                'marble_width': lot.marble_width,
                'marble_sqm': lot.marble_sqm,
                'lot_general': lot.lot_general,
                'marble_thickness': lot.marble_thickness,
                'numero_contenedor': lot.numero_contenedor,
            }
            
            # Buscamos el pedimento del quant correspondiente
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id), ('quantity', '>', 0), ('location_id.usage', '=', 'internal'),
            ], limit=1, order='in_date DESC')
            if quant:
                expected_data['pedimento_number'] = quant.pedimento_number or ''

            # Creamos un diccionario con los datos a verificar/actualizar
            data_to_write = {}
            for field, value in expected_data.items():
                if getattr(line, field) != value:
                    data_to_write[field] = value

            if data_to_write:
                line.write(data_to_write)
        
        result = super()._action_done()
        return result
```

-e ### ./models/stock_quant.py
```
from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    marble_height = fields.Float('Altura (m)', related='lot_id.marble_height', store=True)
    marble_width = fields.Float('Ancho (m)', related='lot_id.marble_width', store=True)
    marble_sqm = fields.Float('m²', related='lot_id.marble_sqm', store=True)
    lot_general = fields.Char('Lote', related='lot_id.lot_general', store=True)
    marble_thickness = fields.Float('Grosor (cm)', related='lot_id.marble_thickness', store=True)
    numero_contenedor = fields.Char('Número de Contenedor', related='lot_id.numero_contenedor', store=True)
```

-e ### ./models/stock_rule.py
```
# models/stock_rule.py

from odoo import models

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom,
            location_id, name, origin, company_id, values
        )

        sale_line_id = values.get('sale_line_id')
        if sale_line_id:
            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            if sale_line.exists():
                marble_data = {
                    'marble_height':    sale_line.marble_height,
                    'marble_width':     sale_line.marble_width,
                    'marble_sqm':       sale_line.marble_sqm,
                    'lot_general':      sale_line.lot_general,
                    'pedimento_number': sale_line.pedimento_number,
                    'marble_thickness': sale_line.marble_thickness,
                    'numero_contenedor': sale_line.numero_contenedor,
                }
                if sale_line.lot_id:
                    marble_data.update({
                        'so_lot_id': sale_line.lot_id.id,
                        'lot_id':    sale_line.lot_id.id,
                    })
                res.update(marble_data)
        else:
            marble_data = {
                'marble_height':    values.get('marble_height', 0.0),
                'marble_width':     values.get('marble_width', 0.0),
                'marble_sqm':       values.get('marble_sqm', 0.0),
                'lot_general':      values.get('lot_general', ''),
                'pedimento_number': values.get('pedimento_number', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
                'numero_contenedor': values.get('numero_contenedor', ''),
            }
            forced_lot = values.get('lot_id')
            if forced_lot:
                marble_data.update({
                    'so_lot_id': forced_lot,
                    'lot_id':    forced_lot,
                })
            res.update(marble_data)

        return res
```
```

-e ### ./views/product_template_views.xml
```
<odoo>
    <record id="product_template_form_pricing_inherit" model="ir.ui.view">
        <field name="name">product.template.form.pricing</field>
        <field name="model">product.template</field>
        <field name="inherit_id" ref="product.product_template_only_form_view"/>
        <field name="arch" type="xml">
            
            <!-- Agregar los precios por m² después del código de barras -->
            <xpath expr="//field[@name='barcode']" position="after">
                <separator string="Precios por Metro Cuadrado"/>
                <group col="3">
                    <field name="price_per_sqm_max"/>
                    <field name="price_per_sqm_avg"/>
                    <field name="price_per_sqm_min"/>
                </group>
               
                <separator string="Configuración de Venta por Lote"/>
                <field name="require_lot_selection_on_sale"/>
            </xpath>
            
        </field>
    </record>
</odoo>
```

-e ### ./views/purchase_order_views.xml
```
<odoo>
    <record id="purchase_order_form_inherit_marble" model="ir.ui.view">
        <field name="name">purchase.order.form.marble</field>
        <field name="model">purchase.order</field>
        <field name="inherit_id" ref="purchase.purchase_order_form"/>
        <field name="arch" type="xml">

            <!-- Vista Formulario -->
            <xpath expr="//field[@name='order_line']/form//field[@name='product_id']" position="after">
                <field name="marble_thickness"/>
                <field name="marble_height"/>
                <field name="marble_width"/>
                <!-- CAMBIO: Se quita readonly="1" para que el campo sea editable -->
                <field name="marble_sqm"/>
                <field name="lot_general"/>
                <field name="numero_contenedor"/>
            </xpath>

            <!-- Vista de Lista (Tree) -->
            <xpath expr="//field[@name='order_line']/list//field[@name='product_id']" position="after">
                <field name="marble_thickness" optional="show"/>
                <field name="marble_height" optional="show"/>
                <field name="marble_width" optional="show"/>
                <!-- CAMBIO: Se quita readonly="1" y se hace opcional -->
                <field name="marble_sqm" optional="show"/>
                <field name="lot_general" optional="show"/>
                <field name="numero_contenedor" optional="show"/>
            </xpath>

            <!-- Vista Kanban -->
            <xpath expr="//field[@name='order_line']/kanban//field[@name='product_id']" position="after">
                <field name="marble_thickness"/>
                <field name="marble_height"/>
                <field name="marble_width"/>
                <!-- CAMBIO: Se quita readonly="1" -->
                <field name="marble_sqm"/>
                <field name="lot_general"/>
                <field name="numero_contenedor"/>
            </xpath>

        </field>
    </record>
</odoo>
```

-e ### ./views/sale_order_views.xml
```
<odoo>
    <!-- Vista Unificada para la Línea de Orden de Venta -->
    <record id="view_order_form_inherit_marble_and_pricing" model="ir.ui.view">
        <field name="name">sale.order.form.inherit.marble.pricing</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale.view_order_form"/>
        <field name="arch" type="xml">

            <!-- Añadimos Nivel de Precio y Precio por m² -->
            <xpath expr="//field[@name='order_line']/form//field[@name='product_id']" position="after">
                <field name="price_level"/>
                <field name="applied_price_per_sqm"
                       readonly="price_level != 'manual'"
                       decoration-info="price_level == 'manual'"
                       decoration-muted="price_level != 'manual'"/>
            </xpath>

            <!-- Añadimos los mismos campos a la vista de lista -->
            <xpath expr="//field[@name='order_line']/list//field[@name='price_unit']" position="before">
                <field name="price_level" optional="show"/>
                <field name="applied_price_per_sqm"
                       optional="show"
                       readonly="price_level != 'manual'"
                       decoration-info="price_level == 'manual'"
                       decoration-muted="price_level != 'manual'"/>
            </xpath>

            <!-- Añadimos Lote/Serie y campos de Mármol -->
            <xpath expr="//field[@name='order_line']/form//field[@name='applied_price_per_sqm']" position="after">
                <field name="lot_id" domain="[('product_id', '=', product_id)]"/>
                <field name="pedimento_number" readonly="1"/>
                <group string="Detalles de Pieza (Editables si no se selecciona lote)">
                    <field name="marble_thickness"/>
                    <field name="marble_height"/>
                    <field name="marble_width"/>
                    <field name="marble_sqm"/>
                    <field name="lot_general"/>
                    <field name="numero_contenedor"/>
                </group>
            </xpath>

            <!-- Añadimos los mismos campos de Lote/Mármol a la vista de lista -->
            <xpath expr="//field[@name='order_line']/list//field[@name='applied_price_per_sqm']" position="after">
                <field name="lot_id" optional="show"/>
                <field name="pedimento_number" readonly="1" optional="show"/>
                <field name="marble_thickness" optional="show"/>
                <field name="marble_height" optional="show"/>
                <field name="marble_width" optional="show"/>
                <field name="marble_sqm" optional="show"/>
                <field name="lot_general" optional="show"/>
                <field name="numero_contenedor" optional="show"/>
            </xpath>

        </field>
    </record>
</odoo>
```

-e ### ./views/stock_move_line_views.xml
```
<odoo>
    <record id="view_move_line_tree_inherit_marble" model="ir.ui.view">
        <field name="name">stock.move.line.tree.marble</field>
        <field name="model">stock.move.line</field>
        <field name="inherit_id" ref="stock.view_move_line_tree"/>
        <field name="arch" type="xml">

            <xpath expr="//field[@name='lot_id']" position="after">
                <field name="marble_thickness"/>
                <field name="marble_height"/>
                <field name="marble_width"/>
                <field name="marble_sqm"/>
                <field name="lot_general"/>
                <field name="numero_contenedor"/>

            </xpath>

        </field>
    </record>
</odoo>
```

-e ### ./views/stock_picking_views.xml
```
<odoo>
    <record id="view_picking_form_inherit_marble" model="ir.ui.view">
        <field name="name">stock.picking.form.marble</field>
        <field name="model">stock.picking</field>
        <field name="inherit_id" ref="stock.view_picking_form"/>
        <field name="arch" type="xml">

            <xpath expr="//field[@name='move_ids_without_package']/list/field[@name='product_id']" position="after">
                
                <!-- WIDGET DUAL PARA LOT_GENERAL -->
                <field name="lot_selection_mode" 
                       invisible="is_outgoing == False"
                       string="Modo"
                       widget="radio"
                       options="{'horizontal': true}"/>
                
                <!-- Campo para seleccionar lote existente (solo en salidas) -->
                <field name="existing_lot_id" 
                       invisible="lot_selection_mode != 'existing' or is_outgoing == False"
                       string="Lote Disponible"
                       placeholder="Seleccione un lote disponible..."/>
                
                <!-- Campo lot_general manual -->
                <field name="lot_general" 
                       readonly="lot_selection_mode == 'existing' and is_outgoing == True"
                       placeholder="Ingrese nombre del lote..."
                       decoration-info="lot_selection_mode == 'manual' or is_outgoing == False"
                       decoration-muted="lot_selection_mode == 'existing'"/>

                <field name="numero_contenedor"
                     readonly="lot_selection_mode == 'existing' and is_outgoing == True"
                     placeholder="Ingrese número de contenedor..."
                     decoration-info="lot_selection_mode == 'manual' or is_outgoing == False"
                     decoration-muted="lot_selection_mode == 'existing'"/>
                
                <!-- Campos de dimensiones -->
                <field name="marble_thickness" 
                       readonly="lot_selection_mode == 'existing' and is_outgoing == True"
                       string="Grosor (cm)"/>
                <field name="marble_height" 
                       readonly="lot_selection_mode == 'existing' and is_outgoing == True"
                       string="Altura (m)"/>
                <field name="marble_width" 
                       readonly="lot_selection_mode == 'existing' and is_outgoing == True"
                       string="Ancho (m)"/>
                <field name="marble_sqm" 
                       readonly="1"
                       string="m²"/>
                
                <!-- Campos invisibles pero funcionales -->
                <field name="lot_id" invisible="1"/>
                 <!-- <field name="so_lot_id" invisible="1"/>
                <field name="available_lot_ids" invisible="1"/>
                <field name="is_outgoing" invisible="1"/>-->
                
            </xpath>

        </field>
    </record>
</odoo>
```

-e ### ./views/stock_quant_views.xml
```
<odoo>
    <record id="view_stock_quant_tree_marble_inherit" model="ir.ui.view">
        <field name="name">stock.quant.tree.marble</field>
        <field name="model">stock.quant</field>
        <field name="inherit_id" ref="stock.view_stock_quant_tree_editable"/>
        <field name="arch" type="xml">

            <xpath expr="//field[@name='lot_id']" position="after">
                <field name="marble_thickness" readonly="1"/>
                <field name="marble_height"/>
                <field name="marble_width"/>
                <field name="marble_sqm"/>
                <field name="lot_general"/>
                <field name="numero_contenedor"/>
            </xpath>

        </field>
    </record>
</odoo>
```

### __init__.py
```python
from . import models
```

### __manifest__.py
```python
{
    'name': 'Marble Serial Tracking',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Track Marble Pieces with Dimensions and Unique Serials',
    'author': 'ALPHAQUEB CONSULTING',
    'website': 'https://alphaqueb.com',
    'company': 'ALPHAQUEB CONSULTING S.A.S.',
    'maintainer': 'ANTONIO QUEB',
    'depends': ['purchase', 'stock',  'sale_management', 'sale_stock', 'marble_pedimento_tracking', 'marble_product_base'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/purchase_order_views.xml',
        'views/stock_move_line_views.xml',
        'views/stock_quant_views.xml',
        'views/stock_picking_views.xml',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',  
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
```

