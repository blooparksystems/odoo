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
from openerp import api, models


class BasePartnerAddressMigration(models.TransientModel):
    _name = 'base.partner.address.migration'

    @api.model
    def migrate_contact_information(self):
        """ This method uses PL/PgSQL language instead of normal
        ORM methods to improve the performance of the migration
        for huge databases. 
        """
        self.env.cr.execute("""
CREATE OR REPLACE
    FUNCTION migrate_contact_information() RETURNS VOID AS $$
DECLARE
    query_part TEXT;
    part RECORD;
    last_id INTEGER;
BEGIN
    query_part := 'SELECT id, name, street, street2, zip,
                          city, state_id, country_id,
                          email, phone, fax, mobile
                   FROM res_partner';
    FOR part IN EXECUTE query_part
    LOOP
        -- Address
        IF (part.street IS NOT NULL)
            OR (part.street2 IS NOT NULL)
            OR (part.zip IS NOT NULL)
            OR (part.city IS NOT NULL)
            OR (part.state_id IS NOT NULL)
            OR (part.country_id IS NOT NULL) THEN
            INSERT INTO res_partner_address (
                create_uid,
                write_uid,
                partner_id,
                type,
                street,
                street2,
                zip,
                city,
                state_id,
                country_id,
                preferred
            ) VALUES (
                1,
                1,
                part.id,
                'default',
                part.street,
                part.street2,
                part.zip,
                part.city,
                part.state_id,
                part.country_id,
                True
            ) RETURNING id INTO last_id;
            UPDATE res_partner
            SET preferred_address=last_id, street=NULL, street2=NULL,
                zip=NULL, city=NULL, state_id=NULL, country_id=NULL
            WHERE id=part.id;
        END IF;

        -- Email
        IF (part.email IS NOT NULL) THEN
            INSERT INTO res_partner_email (
                create_uid,
                write_uid,
                partner_id,
                type,
                name,
                preferred
            ) VALUES (
                1,
                1,
                part.id,
                'private',
                part.email,
                True
            ) RETURNING id INTO last_id;
            UPDATE res_partner
            SET preferred_email=last_id
            WHERE id=part.id;
        END IF;

        -- Phone
        IF (part.phone IS NOT NULL) THEN
            INSERT INTO res_partner_phone (
                create_uid,
                write_uid,
                partner_id,
                type,
                name,
                preferred
            ) VALUES (
                1,
                1,
                part.id,
                'phone',
                part.phone,
                True
            ) RETURNING id INTO last_id;
            UPDATE res_partner
            SET preferred_phone=last_id, phone=NULL
            WHERE id=part.id;
        END IF;

        -- Mobile
        IF (part.mobile IS NOT NULL) THEN
            INSERT INTO res_partner_phone (
                create_uid,
                write_uid,
                partner_id,
                type,
                name
            ) VALUES (
                1,
                1,
                part.id,
                'mobile',
                part.mobile
            ) RETURNING id INTO last_id;
            UPDATE res_partner
            SET preferred_phone=last_id, mobile=NULL
            WHERE id=part.id;
        END IF;

        -- Fax
        IF (part.fax IS NOT NULL) THEN
            INSERT INTO res_partner_phone (
                create_uid,
                write_uid,
                partner_id,
                type,
                name
            ) VALUES (
                1,
                1,
                part.id,
                'fax',
                part.fax
            ) RETURNING id INTO last_id;
            UPDATE res_partner
            SET preferred_phone=last_id, fax=NULL
            WHERE id=part.id;
        END IF;

    END LOOP;
END;
$$ LANGUAGE plpgsql;

SELECT migrate_contact_information();
DROP FUNCTION IF EXISTS migrate_contact_information();
        """)
