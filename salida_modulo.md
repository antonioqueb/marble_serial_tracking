-e ### models/stock_move_line.py
```
# models/stock_move_line.py
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    marble_height    = fields.Float('Altura (m)')
    marble_width     = fields.Float('Ancho (m)')
    marble_sqm       = fields.Float('Metros Cuadrados')
    lot_general      = fields.Char ('Lote General')
    pedimento_number = fields.Char ('Número de Pedimento', size=18)

    # (código de creación automática de lote sigue idéntico)
    # ... resto de tu método create sin cambios ...
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
# models/stock_quant.py
from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    marble_height    = fields.Float(related='lot_id.marble_height', store=True)
    marble_width     = fields.Float(related='lot_id.marble_width',  store=True)
    marble_sqm       = fields.Float(related='lot_id.marble_sqm',    store=True)
    lot_general      = fields.Char (related='lot_id.lot_general',   store=True)
    pedimento_number = fields.Char (related='lot_id.pedimento_number', store=True)
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

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie',
        domain="[('product_id', '=', product_id)]"
    )

    # ─── Datos que bajan al flujo logístico ───
    marble_height     = fields.Float(related='lot_id.marble_height',     store=True, readonly=True)
    marble_width      = fields.Float(related='lot_id.marble_width',      store=True, readonly=True)
    marble_sqm        = fields.Float(related='lot_id.marble_sqm',        store=True, readonly=True)
    lot_general       = fields.Char (related='lot_id.lot_general',       store=True, readonly=True)
    pedimento_number  = fields.Char (related='lot_id.pedimento_number',  store=True, readonly=True)

    # ─── Propagación al procurement / stock.move ───
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
# models/stock_move.py
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    # tracking
    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")
    lot_id    = fields.Many2one('stock.lot', string='Número de Serie (Venta)')

    # mármol + pedimento
    marble_height    = fields.Float('Altura (m)')
    marble_width     = fields.Float('Ancho (m)')
    marble_sqm       = fields.Float('Metros Cuadrados')
    lot_general      = fields.Char ('Lote General')
    pedimento_number = fields.Char ('Número de Pedimento', size=18)

    # ─── utilidades existentes ───
    is_outgoing = fields.Boolean(
        compute='_compute_is_outgoing',
        store=True, string='Es Salida'
    )

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = move.picking_type_id.code == 'outgoing'

    # ─── crear move-line con todos los campos ───
    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)
        vals.update({
            'lot_id':           self.lot_id.id,
            'marble_height':    self.marble_height,
            'marble_width':     self.marble_width,
            'marble_sqm':       self.marble_sqm,
            'lot_general':      self.lot_general,
            'pedimento_number': self.pedimento_number,
        })
        return vals

    # ─── completar líneas existentes ───
    def _create_move_lines(self):
        res = super()._create_move_lines()
        for move in self:
            for line in move.move_line_ids.filtered(lambda l: not l.pedimento_number):
                line.update({
                    'lot_id':           move.lot_id,
                    'marble_height':    move.marble_height,
                    'marble_width':     move.marble_width,
                    'marble_sqm':       move.marble_sqm,
                    'lot_general':      move.lot_general,
                    'pedimento_number': move.pedimento_number,
                })
        return res
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
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )

        # lote forzado
        forced_lot_id = values.get('lot_id')
        if forced_lot_id:
            res['so_lot_id'] = forced_lot_id
            res['lot_id']    = forced_lot_id

        # campos mármol + pedimento
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
# models/stock_lot.py
from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    # …campos ya existentes…
    marble_height = fields.Float('Altura (m)')
    marble_width  = fields.Float('Ancho (m)')
    marble_sqm    = fields.Float('Metros Cuadrados')
    lot_general   = fields.Char('Lote General')

    pedimento_number = fields.Char('Número de Pedimento', size=18, readonly=True)
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

            <!-- ⬇⬇ quitamos pedimento_number: ya lo añadió el módulo de pedimento -->
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

            <!-- quitamos pedimento_number -->
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

            <!-- sin pedimento_number -->
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
                <field name="lot_id" domain="[('product_id', '=', product_id)]"/>
                <field name="marble_height"    readonly="1"/>
                <field name="marble_width"     readonly="1"/>
                <field name="marble_sqm"       readonly="1"/>
                <field name="lot_general"      readonly="1"/>
                <field name="pedimento_number" readonly="1"/>
            </xpath>

            <!-- ─────────── Tree de líneas ─────────── -->
            <xpath expr="//field[@name='order_line']/list//field[@name='product_id']" position="after">
                <field name="lot_id"/>
                <field name="marble_height"    readonly="1"/>
                <field name="marble_width"     readonly="1"/>
                <field name="marble_sqm"       readonly="1"/>
                <field name="lot_general"      readonly="1"/>
                <field name="pedimento_number" readonly="1"/>
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
        <field name="pedimento_number" readonly="1"/>
      </xpath>

      <!-- tree de líneas -->
      <xpath expr="//field[@name='order_line']/list//field[@name='product_id']" position="after">
        <field name="lot_id"/>
        <field name="marble_height"    readonly="1"/>
        <field name="marble_width"     readonly="1"/>
        <field name="marble_sqm"       readonly="1"/>
        <field name="lot_general"      readonly="1"/>
        <field name="pedimento_number" readonly="1"/>
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
