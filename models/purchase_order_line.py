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

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        """
        Compute que respeta valores establecidos desde procurement
        """
        for line in self:
            # Si viene desde procurement, NO recalcular
            if self.env.context.get('from_procurement'):
                _logger.debug(f"[MARBLE-COMPUTE] PO Line ID {line.id}: Respetando valor desde procurement")
                continue
                
            altura = line.marble_height or 0.0
            ancho = line.marble_width or 0.0

            if altura > 0 and ancho > 0:
                line.marble_sqm = altura * ancho
                _logger.debug(f"[MARBLE-COMPUTE] PO Line ID {line.id}: altura={altura}, ancho={ancho} → m²={line.marble_sqm}")
            elif line._origin and line._origin.marble_sqm > 0:
                line.marble_sqm = line._origin.marble_sqm
                _logger.debug(f"[MARBLE-COMPUTE] PO Line ID {line.id}: Manteniendo valor original marble_sqm={line.marble_sqm}")
            else:
                # Solo resetear a 0 si no hay valor previo y es edición manual
                if not getattr(line, '_marble_sqm_from_sale', False):
                    line.marble_sqm = 0.0
                    _logger.debug(f"[MARBLE-COMPUTE] PO Line ID {line.id}: Sin dimensiones ni valor original, establecido en 0")

    @api.onchange('marble_height', 'marble_width', 'lot_general')
    def _onchange_marble_fields(self):
        for line in self:
            _logger.info(f"[MARBLE-ONCHANGE] (onchange) PO Line ID {line.id} → altura={line.marble_height}, ancho={line.marble_width}, lote={line.lot_general}")

    def write(self, vals):
        # Si viene desde procurement, marcar para evitar recálculo
        if self.env.context.get('from_procurement') and 'marble_sqm' in vals:
            for line in self:
                line._marble_sqm_from_sale = True
                _logger.info(f"[MARBLE-WRITE] PO Line {line.id}: Marcando marble_sqm como desde venta")
        
        for line in self:
            _logger.info(f"[MARBLE-WRITE] Intentando escribir en PO Line {line.id} con: {vals}")
        
        res = super().write(vals)
        
        for line in self:
            _logger.info(f"[MARBLE-WRITE] Línea PO {line.id} actualizada - Valores finales:")
            _logger.info(f"  - marble_height: {line.marble_height}")
            _logger.info(f"  - marble_width: {line.marble_width}")
            _logger.info(f"  - marble_sqm: {line.marble_sqm}")
            _logger.info(f"  - lot_general: {line.lot_general}")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _logger.info(f"[MARBLE-CREATE] Creando línea PO con valores: {vals}")
            
            # Si viene marble_sqm desde procurement, marcarlo y respetarlo
            if vals.get('marble_sqm', 0.0) > 0:
                vals['_marble_sqm_from_sale'] = True
                _logger.info(f"[MARBLE-CREATE] Respetando marble_sqm desde procurement: {vals['marble_sqm']}")
        
        lines = super().create(vals_list)
        
        for vals, line in zip(vals_list, lines):
            _logger.info(f"[MARBLE-CREATE] Línea PO creada ID {line.id}:")
            _logger.info(f"  - marble_height: {line.marble_height}")
            _logger.info(f"  - marble_width: {line.marble_width}")
            _logger.info(f"  - marble_sqm: {line.marble_sqm}")
            _logger.info(f"  - lot_general: {line.lot_general}")
        return lines

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        self.ensure_one()
        _logger.info(f"[MARBLE-MOVE-VALS] Ejecutando _prepare_stock_move_vals en PO Line ID {self.id}")
        _logger.info(f"[MARBLE-MOVE-VALS] Datos actuales: altura={self.marble_height}, ancho={self.marble_width}, m²={self.marble_sqm}, lote={self.lot_general}")
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
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