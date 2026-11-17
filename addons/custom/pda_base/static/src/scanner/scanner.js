/** @odoo-module **/

/**
 * Écran principal de l'application PDA.
 *
 * Composant OWL monté via une action client (``pda_base.scanner``). Il ne
 * contient aucune logique métier : il appelle les endpoints JSON-RPC du
 * module (eux-mêmes délégués à ``pda.service``) et affiche le résultat.
 */
import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class PdaScanner extends Component {
    static template = "pda_base.PdaScanner";
    static props = { ...standardActionServiceProps };

    setup() {
        this.notification = useService("notification");
        this.barcodeInput = useRef("barcodeInput");
        this.state = useState({
            barcode: "",
            loading: false,
            product: null,
            error: null,
            locations: [],
            locationsLoaded: false,
            locationsLoading: false,
            showLocations: false,
        });
        onMounted(() => this.focusBarcodeInput());
    }

    /** Redonner le focus au champ de scan (usage PDA au clavier/lecteur). */
    focusBarcodeInput() {
        this.barcodeInput.el?.focus();
    }

    /** Vider le résultat courant et se préparer au scan suivant. */
    resetScan() {
        this.state.barcode = "";
        this.state.product = null;
        this.state.error = null;
        this.focusBarcodeInput();
    }

    /**
     * Envoyer le code-barres saisi à l'endpoint de recherche produit.
     *
     * @returns {Promise<void>}
     */
    async scan() {
        const barcode = this.state.barcode.trim();
        if (!barcode || this.state.loading) {
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        this.state.product = null;
        try {
            const result = await rpc("/pda/api/product/by_barcode", { barcode });
            if (result.success) {
                this.state.product = result;
            } else {
                this.state.error = {
                    code: result.error_code,
                    message: result.message,
                };
            }
        } catch (error) {
            this.notification.add(
                "Impossible de contacter le serveur PDA.",
                { type: "danger" }
            );
            this.state.error = {
                code: "network_error",
                message: "Impossible de contacter le serveur PDA.",
            };
        } finally {
            this.state.loading = false;
        }
    }

    /** Afficher ou masquer la liste des emplacements internes. */
    async toggleLocations() {
        this.state.showLocations = !this.state.showLocations;
        if (!this.state.showLocations || this.state.locationsLoaded) {
            return;
        }
        this.state.locationsLoading = true;
        try {
            const result = await rpc("/pda/api/locations", {});
            if (result.success) {
                this.state.locations = result.locations;
                this.state.locationsLoaded = true;
            } else {
                this.notification.add(result.message, { type: "danger" });
            }
        } catch (error) {
            this.notification.add(
                "Impossible de charger les emplacements.",
                { type: "danger" }
            );
        } finally {
            this.state.locationsLoading = false;
        }
    }
}

registry.category("actions").add("pda_base.scanner", PdaScanner);
