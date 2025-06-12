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
