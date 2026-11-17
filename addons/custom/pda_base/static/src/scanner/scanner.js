/** @odoo-module **/

/**
 * Écran principal de l'application PDA.
 *
 * Composant OWL monté via une action client (``pda_base.scanner``). Il ne
 * contient aucune logique métier : il appelle les endpoints JSON-RPC du
 * module (eux-mêmes délégués à ``pda.service``) et affiche le résultat.
 */
import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { scanBarcode } from "@web/core/barcode/barcode_dialog";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const OPERATIONS = [
    { key: "receipt", label: "Réception", icon: "fa-download" },
    { key: "issue", label: "Sortie", icon: "fa-upload" },
    { key: "transfer", label: "Transfert", icon: "fa-exchange" },
    { key: "inventory", label: "Inventaire", icon: "fa-list-ol" },
];

const OPERATION_ENDPOINTS = {
    receipt: "/pda/api/receipt",
    issue: "/pda/api/issue",
    transfer: "/pda/api/transfer",
    inventory: "/pda/api/inventory",
};

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
            operation: null,
            quantity: "1",
            locationId: "",
            locationDestId: "",
            operationSubmitting: false,
            operationError: null,
        });
        onMounted(() => this.focusBarcodeInput());
    }

    get operations() {
        return OPERATIONS;
    }

    /** Libellé de l'opération en cours de saisie. */
    get operationLabel() {
        const operation = OPERATIONS.find(
            (item) => item.key === this.state.operation
        );
        return operation ? operation.label : "";
    }

    /** L'opération courante nécessite-t-elle un emplacement source ? */
    get needsSource() {
        return ["issue", "transfer", "inventory"].includes(this.state.operation);
    }

    /** L'opération courante nécessite-t-elle un emplacement destination ? */
    get needsDestination() {
        return ["receipt", "transfer"].includes(this.state.operation);
    }

    /** Le formulaire d'opération peut-il être validé ? */
    get canSubmitOperation() {
        if (this.state.operationSubmitting) {
            return false;
        }
        if (this.needsSource && !this.state.locationId) {
            return false;
        }
        if (this.needsDestination && !this.state.locationDestId) {
            return false;
        }
        const quantity = Number(this.state.quantity);
        if (!Number.isFinite(quantity) || quantity < 0) {
            return false;
        }
        return this.state.operation === "inventory" || quantity > 0;
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
        this.state.operation = null;
        this.state.operationError = null;
        this.focusBarcodeInput();
    }

    /**
     * Scanner un code-barres avec la caméra de l'appareil.
     *
     * Réutilise le scanner vidéo natif d'Odoo (BarcodeDetector, avec repli
     * ZXing). La caméra exige un contexte sécurisé (HTTPS ou localhost).
     *
     * @returns {Promise<void>}
     */
    async scanWithCamera() {
        try {
            const barcode = await scanBarcode(this.env, "environment");
            if (barcode) {
                this.state.barcode = barcode;
                await this.scan();
            }
        } catch (error) {
            this.notification.add(
                error?.message || "Impossible d'utiliser la caméra.",
                { type: "danger" }
            );
        }
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
        this.state.operation = null;
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

    /** Ouvrir le formulaire d'une opération de stock. */
    openOperation(operation) {
        this.state.operation = operation;
        this.state.quantity = "1";
        this.state.locationId = "";
        this.state.locationDestId = "";
        this.state.operationError = null;
        this.ensureLocations();
    }

    /** Refermer le formulaire d'opération sans rien valider. */
    closeOperation() {
        this.state.operation = null;
        this.state.operationError = null;
    }

    /** Charger la liste des emplacements internes si nécessaire. */
    async ensureLocations() {
        if (this.state.locationsLoaded || this.state.locationsLoading) {
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

    /** Afficher ou masquer la liste des emplacements internes. */
    async toggleLocations() {
        this.state.showLocations = !this.state.showLocations;
        if (this.state.showLocations) {
            await this.ensureLocations();
        }
    }

    /**
     * Valider l'opération de stock en cours (réception, sortie, transfert ou
     * inventaire) et rafraîchir la fiche produit avec le stock à jour.
     *
     * @returns {Promise<void>}
     */
    async submitOperation() {
        if (!this.canSubmitOperation || !this.state.product) {
            return;
        }
        const params = {
            barcode: this.state.product.barcode,
            quantity: Number(this.state.quantity),
        };
        if (this.needsSource) {
            params.location_id = Number(this.state.locationId);
        }
        if (this.needsDestination) {
            params.location_dest_id = Number(this.state.locationDestId);
        }
        this.state.operationSubmitting = true;
        this.state.operationError = null;
        try {
            const result = await rpc(
                OPERATION_ENDPOINTS[this.state.operation],
                params
            );
            if (result.success) {
                this.state.product = result;
                this.state.operation = null;
                this.notification.add(result.message, { type: "success" });
            } else {
                this.state.operationError = result.message;
            }
        } catch (error) {
            this.notification.add(
                "Impossible de contacter le serveur PDA.",
                { type: "danger" }
            );
            this.state.operationError =
                "Impossible de contacter le serveur PDA.";
        } finally {
            this.state.operationSubmitting = false;
        }
    }
}

registry.category("actions").add("pda_base.scanner", PdaScanner);
