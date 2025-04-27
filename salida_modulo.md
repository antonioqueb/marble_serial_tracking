-e ### models/stock_move_line.py
```
# models/stock_move_line.py
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # ─────────── Campos extendidos ───────────
    marble_height = fields.Float('Altura (m)')
    marble_width  = fields.Float('Ancho (m)')
    marble_sqm    = fields.Float('Metros Cuadrados')
    lot_general   = fields.Char('Lote General')

    # ─────────── Creación automática de lote ───────────
    @api.model_create_multi
    def create(self, vals_list):
        """
        Genera (o reutiliza) un stock.lot si:
        • La línea pertenece a una recepción (picking tipo *incoming*) y
        • Viene un valor para `lot_general` pero no `lot_id`.
        """
        lots_env   = self.env['stock.lot']
        seq_env    = self.env['ir.sequence'].sudo()

        # 🔸 PRE-LOG
        for vals in vals_list:
            _logger.debug("[SML-CREATE|PRE] vals=%s", vals)

        # 1) Lógica de lote antes de llamar a super()
        for vals in vals_list:
            # ► Solo si no hay lote aún y viene 'lot_general'
            if vals.get('lot_id') or not vals.get('lot_general'):
                continue

            # ► Determinar si la línea es de una recepción (incoming)
            #    Durante el create no existe aún move_line, usamos el contexto
            picking_code = vals.get('picking_code')  # cuando viene de scanner
            if not picking_code:
                # ⇒ Caso normal: obtenemos el move para checar su picking
                move = self.env['stock.move'].browse(vals.get('move_id'))
                picking_code = move.picking_type_id.code

            if picking_code != 'incoming':
                _logger.debug("[SML-CREATE] No es 'incoming' (code=%s) → sin lote", picking_code)
                continue

            lot_general = vals['lot_general']
            product_id  = vals.get('product_id')

            # 1.1) Reutilizar lote existente
            existing_lot = lots_env.search([
                ('product_id', '=', product_id),
                ('lot_general', '=', lot_general)
            ], limit=1)
            if existing_lot:
                vals['lot_id'] = existing_lot.id
                _logger.info("[LOT-AUTO] Reutilizado lote %s (ID %s) para producto %s",
                             existing_lot.name, existing_lot.id, product_id)
                continue

            # 1.2) Crear nuevo lote con secuencia específica
            seq_code = f"marble.serial.{lot_general}"
            sequence = seq_env.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = seq_env.create({
                    'name': _('Secuencia Mármol %s') % lot_general,
                    'code': seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })
                _logger.debug("[SEQ] Creada nueva secuencia %s", seq_code)

            lot_name = sequence.next_by_id()
            vals['lot_id'] = lots_env.create({
                'name':           lot_name,
                'product_id':     product_id,
                'company_id':     vals.get('company_id'),
                'marble_height':  vals.get('marble_height'),
                'marble_width':   vals.get('marble_width'),
                'marble_sqm':     vals.get('marble_sqm'),
                'lot_general':    lot_general,
            }).id
            _logger.info("[LOT-AUTO] Creado lote %s para producto %s (general=%s)",
                         lot_name, product_id, lot_general)

        # 2) Crear las líneas normalmente
        move_lines = super().create(vals_list)

        # 🔸 POST-LOG
        for line in move_lines:
            _logger.debug(
                "[SML-CREATE|POST] line_id=%s lot=%s height=%s width=%s sqm=%s",
                line.id, line.lot_id.name, line.marble_height, line.marble_width, line.marble_sqm
            )
        return move_lines
```

-e ### models/purchase_order_line.py
```
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)
# __all__ = ['PurchaseOrderLine']
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    marble_height = fields.Float('Altura (m)', store=True)
    marble_width = fields.Float('Ancho (m)', store=True)
    marble_sqm = fields.Float('Metros Cuadrados', compute='_compute_marble_sqm', store=True)
    lot_general = fields.Char('Lote General', store=True)

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for line in self:
            altura = line.marble_height or 0.0
            ancho = line.marble_width or 0.0
            line.marble_sqm = altura * ancho
            _logger.debug(f"[MARBLE-COMPUTE] PO Line ID {line.id}: altura={altura}, ancho={ancho} → m²={line.marble_sqm}")

    @api.onchange('marble_height', 'marble_width', 'lot_general')
    def _onchange_marble_fields(self):
        for line in self:
            _logger.info(f"[MARBLE-ONCHANGE] (onchange) PO Line ID {line.id} → altura={line.marble_height}, ancho={line.marble_width}, lote={line.lot_general}")

    def write(self, vals):
        for line in self:
            _logger.info(f"[MARBLE-WRITE] Intentando escribir en PO Line {line.id} con: {vals}")
        res = super().write(vals)
        for line in self:
            _logger.info(f"[MARBLE-WRITE] Línea PO {line.id} actualizada correctamente")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for vals, line in zip(vals_list, lines):
            _logger.info(f"[MARBLE-CREATE] Línea PO creada ID {line.id} con: altura={vals.get('marble_height')}, ancho={vals.get('marble_width')}, lote={vals.get('lot_general')}")
        return lines

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        self.ensure_one()  # Nos aseguramos de estar en singleton
        _logger.info(f"[MARBLE-MOVE-VALS] Ejecutando _prepare_stock_move_vals en PO Line ID {self.id}")
        _logger.info(f"[MARBLE-MOVE-VALS] Datos actuales: altura={self.marble_height}, ancho={self.marble_width}, m²={self.marble_sqm}, lote={self.lot_general}")
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
        })
        _logger.info(f"[MARBLE-MOVE-VALS] Valores enviados al move: {vals}")
        return vals

    def _create_stock_moves(self, picking):
        res = self.env['stock.move']
        for line in self:
            _logger.info(f"[MARBLE-MOVE-CREATE] Ejecutando _create_stock_moves en PO Line ID {line.id}")
            moves = super(PurchaseOrderLine, line)._create_stock_moves(picking)
            _logger.info(f"[MARBLE-MOVE-CREATE] Total moves creados para PO Line ID {line.id}: {len(moves)}")
            for move in moves:
                _logger.info(f"[MARBLE-MOVE-CREATE] Move ID {move.id} creado para producto: {move.product_id.display_name}")
            res |= moves
        return res
# Funcional module
```

-e ### models/stock_quant.py
```
from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    marble_height = fields.Float('Altura (m)', related='lot_id.marble_height', store=True)
    marble_width = fields.Float('Ancho (m)', related='lot_id.marble_width', store=True)
    marble_sqm = fields.Float('Metros Cuadrados', related='lot_id.marble_sqm', store=True)
    lot_general = fields.Char('Lote General', related='lot_id.lot_general', store=True)
```

-e ### models/__init__.py
```
from . import purchase_order_line
from . import stock_move_line
from . import stock_quant
from . import stock_lot
from . import stock_move
from . import purchase_order
from . import sale_order_line
from . import stock_rule
```

-e ### models/sale_order_line.py
```
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
            'pedimento_number': self.pedimento_number,
        })
        return vals
```

-e ### models/purchase_order.py
```
from odoo import models
import logging
# FUNCIONAL

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
                _logger.info(f"[MARBLE-FIX] Línea PO encontrada: ID {po_line.id} → altura={po_line.marble_height}, ancho={po_line.marble_width}, m²={po_line.marble_sqm}, lote={po_line.lot_general}")
                move_vals.update({
                    'marble_height': po_line.marble_height or 0.0,
                    'marble_width': po_line.marble_width or 0.0,
                    'marble_sqm': po_line.marble_sqm or 0.0,
                    'lot_general': po_line.lot_general or '',
                })
            else:
                _logger.warning(f"[MARBLE-FIX] No se encontró línea PO para move_vals: {move_vals}")
        return res
```

-e ### models/stock_move.py
```
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    # Campos de tracking desde la venta
    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")
    lot_id = fields.Many2one('stock.lot', string='Número de Serie (Venta)')  # Visible solo en entregas (ver vista)

    # Campos de mármol
    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados')
    lot_general = fields.Char('Lote General')

    # Campo computado para distinguir entregas
    is_outgoing = fields.Boolean(
        string='Es Salida',
        compute='_compute_is_outgoing',
        store=True
    )

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = move.picking_type_id.code == 'outgoing'

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        """
        Mantiene la lógica original de crear la move line 
        con los campos de mármol y el lote vinculado a la venta.
        """
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)
        vals.update({
            'lot_id': self.lot_id.id,
            'marble_height': self.marble_height,
            'marble_width': self.marble_width,
            'marble_sqm': self.marble_sqm,
            'lot_general': self.lot_general,
        })
        _logger.info(f"Move line creado con valores: {vals}")
        return vals

    def _create_move_lines(self):
        """
        Tras crear las líneas, completa los valores de mármol
        si vienen vacíos en el move line. Incluye la asignación
        del lote asociado a la venta.
        """
        res = super()._create_move_lines()
        for move in self:
            for line in move.move_line_ids:
                if not line.lot_id and move.lot_id:
                    line.lot_id = move.lot_id
                if not line.marble_height:
                    line.marble_height = move.marble_height
                if not line.marble_width:
                    line.marble_width = move.marble_width
                if not line.marble_sqm:
                    line.marble_sqm = move.marble_sqm
                if not line.lot_general:
                    line.lot_general = move.lot_general
        return res

    def _action_assign(self):
        """
        Sobrescribimos la asignación de stock para forzar que,
        si hay un lote específico 'so_lot_id' proveniente de la venta,
        se reserve en ese lote y no según la política FIFO (PEPS).
        """
        # Primero dejamos que Odoo haga la reserva estándar
        super()._action_assign()

        # Luego forzamos la reserva en el lote si 'so_lot_id' está presente
        for move in self.filtered(lambda m: m.state in ('confirmed','partially_available','waiting')):
            if move.product_id.tracking != 'none' and move.so_lot_id:
                lot = move.so_lot_id
                _logger.info(f"Forzando reserva en lote {lot.name} para Move {move.id} ({move.product_id.display_name})")

                already_reserved = sum(move.move_line_ids.mapped('product_uom_qty'))
                missing_to_reserve = move.product_uom_qty - already_reserved

                if missing_to_reserve > 0:
                    available_qty = self.env['stock.quant']._get_available_quantity(
                        move.product_id,
                        move.location_id,
                        lot_id=lot,
                        package_id=False,
                        owner_id=False,
                        strict=True
                    )
                    if available_qty <= 0:
                        _logger.warning(f"No hay stock disponible en el lote {lot.name}.")
                        continue

                    qty_to_reserve = min(missing_to_reserve, available_qty)

                    existing_line = move.move_line_ids.filtered(lambda ml: ml.lot_id == lot)
                    if existing_line:
                        existing_line.product_uom_qty += qty_to_reserve
                    else:
                        self.env['stock.move.line'].create({
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'lot_id': lot.id,
                            'product_uom_qty': qty_to_reserve,
                        })
        return True
```

-e ### models/stock_rule.py
```
# models/stock_rule.py
from odoo import models

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        """
        *Extendemos* la salida original para inyectar:
        • Lote forzado
        • Datos de mármol
        • Número de pedimento
        """
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )

        # Lote forzado (si viene desde la venta)
        forced_lot = values.get('lot_id')
        if forced_lot:
            res['so_lot_id'] = forced_lot
            res['lot_id']    = forced_lot

        # Datos adicionales
        res.update({
            'marble_height':    values.get('marble_height', 0.0),
            'marble_width':     values.get('marble_width',  0.0),
            'marble_sqm':       values.get('marble_sqm',    0.0),
            'lot_general':      values.get('lot_general',   ''),
            'pedimento_number': values.get('pedimento_number', ''),
        })
        return res
```

-e ### models/stock_lot.py
```
from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados')
    lot_general = fields.Char('Lote General')
```

-e ### views/purchase_order_views.xml
```
<odoo>
    <record id="purchase_order_form_inherit_marble" model="ir.ui.view">
        <field name="name">purchase.order.form.marble</field>
        <field name="model">purchase.order</field>
        <field name="inherit_id" ref="purchase.purchase_order_form"/>
        <field name="arch" type="xml">

            <xpath expr="//field[@name='order_line']/form//field[@name='product_id']" position="after">
                <field name="marble_height"/>
                <field name="marble_width"/>
                <field name="marble_sqm" readonly="1"/>
                <field name="lot_general"/>
            </xpath>

            <xpath expr="//field[@name='order_line']/list//field[@name='product_id']" position="after">
                <field name="marble_height"/>
                <field name="marble_width"/>
                <field name="marble_sqm" readonly="1"/>
                <field name="lot_general"/>
            </xpath>

            <xpath expr="//field[@name='order_line']/kanban//field[@name='product_id']" position="after">
                <field name="marble_height"/>
                <field name="marble_width"/>
                <field name="marble_sqm" readonly="1"/>
                <field name="lot_general"/>
            </xpath>

        </field>
    </record>
</odoo>
```

-e ### views/stock_picking_views.xml
```
<odoo>
    <record id="view_picking_form_inherit_marble" model="ir.ui.view">
        <field name="name">stock.picking.form.marble</field>
        <field name="model">stock.picking</field>
        <field name="inherit_id" ref="stock.view_picking_form"/>
        <field name="arch" type="xml">

            <xpath expr="//field[@name='move_ids_without_package']/list/field[@name='product_id']"
                   position="after">
                <field name="lot_id"           readonly="1" invisible="not is_outgoing"/>
                <field name="marble_height"    readonly="1"/>
                <field name="marble_width"     readonly="1"/>
                <field name="marble_sqm"       readonly="1"/>
                <field name="lot_general"      readonly="1"/>
            </xpath>

        </field>
    </record>
</odoo>
```

-e ### views/stock_quant_views.xml
```
<odoo>
    <record id="view_stock_quant_tree_marble_inherit" model="ir.ui.view">
        <field name="name">stock.quant.tree.marble</field>
        <field name="model">stock.quant</field>
        <field name="inherit_id" ref="stock.view_stock_quant_tree_editable"/>
        <field name="arch" type="xml">

            <xpath expr="//field[@name='lot_id']" position="after">
                <field name="marble_height"/>
                <field name="marble_width"/>
                <field name="marble_sqm"/>
                <field name="lot_general"/>
            </xpath>

        </field>
    </record>
</odoo>
```

-e ### views/stock_move_line_views.xml
```
<odoo>
    <record id="view_move_line_tree_inherit_marble" model="ir.ui.view">
        <field name="name">stock.move.line.tree.marble</field>
        <field name="model">stock.move.line</field>
        <field name="inherit_id" ref="stock.view_move_line_tree"/>
        <field name="arch" type="xml">

            <xpath expr="//field[@name='lot_id']" position="after">
                <field name="marble_height"/>
                <field name="marble_width"/>
                <field name="marble_sqm"/>
                <field name="lot_general"/>
            </xpath>

        </field>
    </record>
</odoo>
```

-e ### views/sale_order_views.xml
```
<odoo>
    <record id="view_sale_order_form_marble_inherit" model="ir.ui.view">
        <field name="name">sale.order.form.marble</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale.view_order_form"/>
        <field name="arch" type="xml">

            <!-- ─────────── Formulario de la línea ─────────── -->
            <xpath expr="//field[@name='order_line']/form//field[@name='product_id']" position="after">
                <!-- Lote seleccionado -->
                <field name="lot_id" domain="[('product_id', '=', product_id)]"/>
                <!-- Pedimento (solo lectura) -->
                <field name="pedimento_number" readonly="1"/>
                <!-- Datos de mármol -->
                <field name="marble_height" readonly="1"/>
                <field name="marble_width"  readonly="1"/>
                <field name="marble_sqm"    readonly="1"/>
                <field name="lot_general"   readonly="1"/>
            </xpath>

            <!-- ─────────── Tree de líneas ─────────── -->
            <xpath expr="//field[@name='order_line']/list//field[@name='product_id']" position="after">
                <!-- Lote seleccionado -->
                <field name="lot_id"/>
                <!-- Pedimento (solo lectura) -->
                <field name="pedimento_number" readonly="1"/>
                <!-- Datos de mármol -->
                <field name="marble_height" readonly="1"/>
                <field name="marble_width"  readonly="1"/>
                <field name="marble_sqm"    readonly="1"/>
                <field name="lot_general"   readonly="1"/>
            </xpath>

        </field>
    </record>
</odoo>
```

-e ### views/stock_lot_views.xml
```
<odoo>
  <record id="view_sale_order_form_marble_inherit" model="ir.ui.view">
    <field name="name">sale.order.form.marble</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">

      <!-- formulario de línea -->
      <xpath expr="//field[@name='order_line']/form//field[@name='product_id']" position="after">
        <field name="lot_id" domain="[('product_id', '=', product_id)]"/>
        <field name="marble_height"    readonly="1"/>
        <field name="marble_width"     readonly="1"/>
        <field name="marble_sqm"       readonly="1"/>
        <field name="lot_general"      readonly="1"/>
      </xpath>

      <!-- tree de líneas -->
      <xpath expr="//field[@name='order_line']/list//field[@name='product_id']" position="after">
        <field name="lot_id"/>
        <field name="marble_height"    readonly="1"/>
        <field name="marble_width"     readonly="1"/>
        <field name="marble_sqm"       readonly="1"/>
        <field name="lot_general"      readonly="1"/>
      </xpath>

    </field>
  </record>
</odoo>
```

### __init__.py
```
from . import models
```
### __manifest__.py
```
{
    'name': 'Marble Serial Tracking',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Track Marble Pieces with Dimensions and Unique Serials',
    'author': 'ALPHAQUEB CONSULTING',
    'website': 'https://alphaqueb.com',
    'company': 'ALPHAQUEB CONSULTING S.A.S.',
    'maintainer': 'ANTONIO QUEB',
    'depends': ['purchase', 'stock',  'sale_management', 'sale_stock', 'marble_pedimento_tracking'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/purchase_order_views.xml',
        'views/stock_move_line_views.xml',
        'views/stock_quant_views.xml',
        'views/stock_lot_views.xml',
        'views/stock_picking_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
```
