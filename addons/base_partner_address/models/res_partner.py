# -*- coding: utf-8 -*-
##############################################################################
#
# Odoo, an open source suite of business apps
# This module copyright (C) 2015 bloopark systems (<http://bloopark.de>).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp import _, api, fields, models
from openerp.exceptions import ValidationError

CONTACTS = ['address', 'email', 'phone']


class ResPartner(models.Model):
    """Partner updates like new address handling, default values etc."""
    _inherit = 'res.partner'

    website = fields.Char('Website', size=128,
                          help="Website of Partner or Company")
    type = fields.Selection(
        [('default', 'Default'), ('invoice', 'Invoice'),
         ('delivery', 'Shipping'), ('contact', 'Contact'), ('other', 'Other'),
         ('address', 'Address')], 'Address Type',
        help="Used to select automatically the right address according to the"
             "context in sales and purchases documents.")
    
    preferred_address = fields.Many2one('res.partner.address', 'Preferred Address')
    partner_address_ids = fields.One2many('res.partner.address', 'partner_id',
                                          'Addresses')
    
    preferred_email = fields.Many2one('res.partner.email', 'Preferred Email')
    partner_email_ids = fields.One2many('res.partner.email', 'partner_id',
                                        'Emails')
    
    preferred_phone = fields.Many2one('res.partner.phone', 'Preferred Phone')
    partner_phone_ids = fields.One2many('res.partner.phone', 'partner_id',
                                        'Phones')

    @api.model
    def get_address(self, addr_type, first=False):
        """Return address of type addr_type or first address."""
        rpa_obj = self.env['res.partner.address']
        # it is possible that self._uid is None, especially after a server
        # restart, we would get an error like "AccessError: ('No value found
        # for res.partner(21,).partner_address_ids', None)" without sudo()
        address = rpa_obj.sudo().search(
            [('partner_id', '=', self.id), ('type', '=', addr_type)],
            order='id ASC', limit=1)
        if address:
            return address

        if first:
            address = rpa_obj.sudo().search([('partner_id', '=', self.id)],
                                            order='id ASC', limit=1)
            if address:
                return address

        return False

    @api.model
    def get_phone(self, phone_type):
        """Return first phone number of type phone_type."""
        domain = [('partner_id', '=', self.id)]
        if phone_type:
            domain.append(('type', '=', phone_type))
        # it is possible that self._uid is None, especially after a server
        # restart, we would get an error like "AccessError: ('No value found
        # for res.partner(21,).partner_address_ids', None)" without sudo()
        phone = self.env['res.partner.phone'].sudo().search(
            domain, order='id ASC', limit=1)

        return phone or False

    @api.onchange('name')
    def name_change(self):
        """Set parent_id forwarded from partner_shipping_id in sale orders."""
        if not self.parent_id and self._context.get('parent_id', False):
            self.parent_id = self._context['parent_id']

    @api.model
    def default_get(self, fields):
        """Set default values for company partners and partner addresses."""
        res = super(ResPartner, self).default_get(fields)

        # we don't want a default name for company contacts
        if self._context.get('is_company', False):
            res['name'] = ''

        return res

    @api.model
    def _handle_first_contact_creation(self, partner):
        """Skip function to avoid a problem when creating partners.

        Problem: If you create a partner in contacts (not in sale or purchase
        section) and assign one address the partner is flagged as company. It
        also fixes a problem when you create more than one address at a time.

        Original function description: On creation of first contact for a
        company (or root) that has no address, assume contact address was meant
        to be company address.
        """
        pass

    @api.model
    def create(self, vals):
        for field in CONTACTS:
            field_ids = 'partner_%s_ids' % field
            if len(vals.get(field_ids, [])) == 1:
                vals[field_ids][0][2]['preferred'] = True
        return super(ResPartner, self).create(vals)

    @api.multi
    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        fields_to_update = []
        for field in CONTACTS:
            field_ids = 'partner_%s_ids' % field
            if field_ids in vals:
                fields_to_update.append(field_ids)
        if fields_to_update:
            for rec in self:
                for f in fields_to_update:
                    contacts = getattr(rec, f)
                    if len(contacts) == 1 and not contacts.preferred:
                        contacts.write({'preferred': True})
        return res

    @api.multi
    def unlink(self):
        """Remove all contact information if partner will be removed."""
        for partner in self:
            for field in CONTACTS:
                field_ids = 'partner_%s_ids' % field
                contacts = getattr(partner, field_ids)
                if contacts:
                    contacts.unlink()
        return super(ResPartner, self).unlink()

    @api.model
    def _display_address(self, partner, without_company=False):
        """Overwrite module: base.

        Changed address line order, zip before city and excluding of
        state_code.
        """
        # get the information that will be injected into the display format
        # get the address format

        addr = partner.preferred_address
        if addr:
            address_format = addr.country_id and \
                addr.country_id.address_format or \
                "%(street)s\n%(street2)s\n%(zip)s %(city)s\n%(country_name)s"

            company_name = ''
            if addr.partner_id.is_company:
                company_name = addr.partner_id.name
            elif addr.partner_id.parent_id and \
                    addr.partner_id.parent_id.is_company:
                company_name = addr.partner_id.parent_id.name

            args = {
                'state_code': addr.state_id and addr.state_id.code or '',
                'state_name': addr.state_id and addr.state_id.name or '',
                'country_code': addr.country_id and addr.country_id.code or '',
                'country_name': addr.country_id and addr.country_id.name or '',
                'company_name': company_name,
            }
            for field in addr._address_fields():
                args[field] = getattr(addr, field) or ''
            if without_company:
                args['company_name'] = ''
            elif addr.partner_id.is_company or \
                    (addr.partner_id.parent_id and
                     addr.partner_id.parent_id.is_company):
                address_format = '%(company_name)s\n' + address_format
            return address_format % args

        return ''

    @api.constrains('partner_address_ids')
    def _check_partner_address(self):
        """In addition check if partner has exactly one address ticked as
        preferred address.
        """
        if self.partner_address_ids \
                and len(self.partner_address_ids) > 1 \
                and not self.partner_address_ids.filtered('preferred'):
            raise ValidationError(
                _('You have to tick exact one address as preferred '
                  'address.'))

    @api.multi
    def address_get_all(self, adr_pref=None):
        """Copy of address_get function embrace the new address handling.

        Because we don't know how big are the impacts of this changings we
        copied the function and didn't overwrite this. This custom function is
        used in onchange_partner_id of sale.py.
        """
        adr_pref = set(adr_pref or [])
        if 'default' not in adr_pref:
            adr_pref.add('default')
        result = {}
        for partner in self:
            for adr_type in adr_pref:
                result[adr_type] = partner.id
            return result
        return result

    def _address_fields(self, cr, uid, context=None):
        """Return empty partner address list.

        We only use address data in res.partner.address we don't use address
        data in res.partner anymore.
        """
        return []

    def clean_preferred(self, contact_type):
        if contact_type not in CONTACTS:
            raise ValidationError(
                _('Contact type not allowed for partners.'))
        model = self.env['res.partner.%s' % contact_type]
        preferred_contact = model.search([
            ('preferred', '=', True),
            ('partner_id', '=', self.id)
        ])
        if preferred_contact:
            preferred_contact.write({'preferred': False})

    def set_preferred(self, contact_type, contact_sub_type, contact_info):
        if contact_type not in CONTACTS:
            raise ValidationError(
                _('Contact type not allowed for partners.'))
        model = self.env['res.partner.%s' % contact_type]
        self.clean_preferred(contact_type)
        domain = [
            ('name', '=', contact_info),
            ('type', '=', contact_sub_type),
            ('partner_id', '=', self.id)
        ]
        contact = model.search(domain, limit=1)
        if contact:
            contact.write({'preferred': True})
        else:
            values = {x[0]: x[2] for x in domain}.update({'preferred': True})
            contact = model.create(values)
        return contact

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        """ Search for address fields in contact information related to res.partner.address,
         res.partner.email and res.partner.phone instead of the fields int the current model. """
        address_fields = ['street', 'street2', 'zip', 'city']
        email_fields = ['email']
        phone_fields = ['phone', 'fax', 'mobile']
        for arg in args:
            if isinstance(arg, list) and arg[0] in address_fields:
                arg[0] = 'preferred_address.%s' % arg[0]
            elif isinstance(arg, list) and arg[0] in email_fields:
                arg[0] = 'preferred_email.name'
            elif isinstance(arg, list) and arg[0] in phone_fields:
                arg[0] = 'preferred_phone.name'
        return super(ResPartner, self).search(cr, user, args, offset=offset, limit=limit,
                                              order=order, context=context, count=count)
