from odoo import models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        res = super().button_confirm()
        self.mapped('picking_ids')._action_assign()  # Forza la creación inmediata de move_lines
        return res
