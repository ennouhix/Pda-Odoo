/** @odoo-module **/

/**
 * Écran principal de l'application PDA.
 *
 * Composant OWL monté via une action client (``pda_base.scanner``). Il ne
 * contient aucune logique métier : il appelle les endpoints JSON-RPC du
 * module (eux-mêmes délégués à ``pda.service``) et affiche le résultat.
 *
 * Parcours pensé pour un usage terrain :
 *
 * 1. choix de l'opération (réception, sortie, transfert, inventaire) ;
 * 2. scan du produit (douchette, clavier ou caméra) ;
 * 3. sélection de l'emplacement en le touchant ou en scannant son étiquette ;
 * 4. quantité au pavé numérique, puis validation immédiate.
 */
import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { scanBarcode } from "@web/core/barcode/barcode_dialog";
import { isBarcodeScannerSupported } from "@web/core/barcode/barcode_video_scanner";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const OPERATIONS = [
    {
        key: "receipt",
        label: "Réception",
        icon: "fa-download",
        hint: "Entrée de marchandise",
    },
    {
        key: "issue",
        label: "Sortie",
        icon: "fa-upload",
        hint: "Consommation, expédition",
    },
    {
        key: "transfer",
        label: "Transfert",
        icon: "fa-exchange",
        hint: "Déplacement interne",
    },
    {
        key: "inventory",
        label: "Inventaire",
        icon: "fa-list-ol",
        hint: "Correction après comptage",
    },
];

const OPERATION_ENDPOINTS = {
    receipt: "/pda/api/receipt",
    issue: "/pda/api/issue",
    transfer: "/pda/api/transfer",
    inventory: "/pda/api/inventory",
};

const SUBMIT_LABELS = {
    receipt: "Valider la réception",
    issue: "Valider la sortie",
    transfer: "Valider le transfert",
    inventory: "Corriger le stock",
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
            success: null,
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

    get username() {
        return user.name || "";
    }

    get operations() {
        return OPERATIONS;
    }

    /** Opération actuellement sélectionnée. */
    get mode() {
        const operation = OPERATIONS.find(
            (item) => item.key === this.state.operation
        );
        return operation || null;
    }

    /** Libellé de l'opération en cours de saisie. */
    get operationLabel() {
        return this.mode ? this.mode.label : "";
    }

    /** Titre du sélecteur d'opération. */
    get modeHeading() {
        return this.state.product
            ? "Choisir une opération"
            : "Que voulez-vous faire ?";
    }

    /** Libellé du bouton de validation. */
    get submitLabel() {
        return SUBMIT_LABELS[this.state.operation] || "Valider";
    }

    get scanPlaceholder() {
        return this.state.operation
            ? "Produit ou emplacement…"
            : "Scannez ou saisissez un code-barres";
    }

    /** L'opération courante nécessite-t-elle un emplacement source ? */
    get needsSource() {
        return ["issue", "transfer", "inventory"].includes(
            this.state.operation
        );
    }

    /** L'opération courante nécessite-t-elle un emplacement destination ? */
    get needsDestination() {
        return ["receipt", "transfer"].includes(this.state.operation);
    }

    /** Une quantité nulle n'a de sens que pour un inventaire. */
    get minQuantity() {
        return this.state.operation === "inventory" ? 0 : 1;
    }

    /** Quantité disponible du produit dans l'emplacement source choisi. */
    get sourceLine() {
        if (!this.state.product) {
            return null;
        }
        const locationId = Number(this.state.locationId);
        const locations = this.state.product.locations || [];
        return locations.find((line) => line.location_id === locationId) || null;
    }

    /** Le formulaire d'opération peut-il être validé ? */
    get canSubmitOperation() {
        if (this.state.operationSubmitting) {
            return false;
        }
        if (this.state.quantity.trim() === "") {
            return false;
        }
        if (this.needsSource && !this.state.locationId) {
            return false;
        }
        if (this.needsDestination && !this.state.locationDestId) {
            return false;
        }
        const quantity = Number(this.state.quantity);
        if (!Number.isFinite(quantity) || quantity < this.minQuantity) {
            return false;
        }
        return this.state.operation === "inventory" || quantity > 0;
    }

    /** Formater une quantité pour l'affichage (séparateurs français). */
    formatQty(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) {
            return "";
        }
        return new Intl.NumberFormat("fr-FR", {
            maximumFractionDigits: 2,
        }).format(number);
    }

    /** Dernier segment d'un chemin d'emplacement (« WH/Stock/A1 » → « A1 »). */
    shortLocationName(name) {
        const parts = String(name || "").split("/");
        return parts[parts.length - 1] || name;
    }

    /** Cette ligne de stock correspond-elle à l'emplacement source choisi ? */
    isLineSelected(line) {
        return String(line.location_id) === this.state.locationId;
    }

    /** Masquer la confirmation de la dernière opération. */
    dismissSuccess() {
        this.state.success = null;
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
        this.state.success = null;
        this.state.quantity = "1";
        this.state.locationId = "";
        this.state.locationDestId = "";
        this.state.operationError = null;
        this.focusBarcodeInput();
    }

    /** Choisir l'opération à effectuer (avant ou après le scan). */
    selectMode(operation) {
        this.state.operation = operation;
        this.state.operationError = null;
        this.state.success = null;
        this.state.locationId = "";
        this.state.locationDestId = "";
        this.state.quantity = operation === "inventory" ? "" : "1";
        this.ensureLocations();
        this.focusBarcodeInput();
    }

    /** Abandonner l'opération en cours (le produit reste affiché). */
    closeOperation() {
        this.state.operation = null;
        this.state.operationError = null;
    }

    /** Ajuster la quantité au pavé (+ / −). */
    adjustQuantity(delta) {
        const current = Number(this.state.quantity) || 0;
        const next = Math.max(this.minQuantity, current + delta);
        this.state.quantity = String(next);
    }

    /** Reprendre la quantité constatée = stock actuel de l'emplacement. */
    useCurrentStock() {
        if (this.sourceLine) {
            this.state.quantity = String(this.sourceLine.quantity);
        }
    }

    /** Pré-remplir la quantité d'inventaire avec le stock de l'emplacement. */
    onSourceChange(ev) {
        this.state.locationId = ev.target.value;
        if (this.state.operation === "inventory") {
            this.state.quantity = this.sourceLine
                ? String(this.sourceLine.quantity)
                : "0";
        }
    }

    /**
     * Affecter un emplacement au champ attendu par l'opération :
     * la source d'abord, puis la destination.
     */
    assignLocation(location) {
        if (this.needsSource && !this.state.locationId) {
            this.state.locationId = String(location.id);
            if (this.state.operation === "inventory") {
                this.state.quantity = this.sourceLine
                    ? String(this.sourceLine.quantity)
                    : "0";
            }
        } else if (this.needsDestination && !this.state.locationDestId) {
            this.state.locationDestId = String(location.id);
        } else if (this.needsSource) {
            this.state.locationId = String(location.id);
            if (this.state.operation === "inventory") {
                this.state.quantity = this.sourceLine
                    ? String(this.sourceLine.quantity)
                    : "0";
            }
        } else if (this.needsDestination) {
            this.state.locationDestId = String(location.id);
        } else {
            return;
        }
        this.notification.add(
            `Emplacement : ${this.shortLocationName(location.name)}`,
            { type: "info" }
        );
    }

    /** Sélectionner un emplacement en touchant une ligne de stock. */
    selectLine(line) {
        if (!this.state.operation) {
            return;
        }
        const location =
            this.state.locations.find((item) => item.id === line.location_id)
            || { id: line.location_id, name: line.location_name };
        this.assignLocation(location);
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
        if (!isBarcodeScannerSupported()) {
            this.notification.add(
                "Caméra indisponible : ouvrez Odoo en HTTPS ou sur localhost, "
                + "puis autorisez l'accès à la caméra.",
                { type: "warning" }
            );
            return;
        }
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
     * Traiter le code-barres saisi : étiquette d'emplacement si une opération
     * est en cours, sinon recherche produit.
     *
     * @returns {Promise<void>}
     */
    async scan() {
        const barcode = this.state.barcode.trim();
        if (!barcode || this.state.loading) {
            return;
        }
        if (this.state.operation) {
            const location = this.state.locations.find(
                (item) =>
                    item.barcode
                    && item.barcode.toLowerCase() === barcode.toLowerCase()
            );
            if (location) {
                this.assignLocation(location);
                this.state.barcode = "";
                this.focusBarcodeInput();
                return;
            }
        }
        this.state.loading = true;
        this.state.error = null;
        this.state.success = null;
        this.state.product = null;
        this.state.operationError = null;
        try {
            const result = await rpc("/pda/api/product/by_barcode", { barcode });
            if (result.success) {
                this.state.product = result;
                this.state.barcode = "";
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
            this.focusBarcodeInput();
        }
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
                this.state.success = { message: result.message };
                this.state.quantity = this.state.operation === "inventory"
                    ? ""
                    : "1";
                this.state.operationError = null;
                this.focusBarcodeInput();
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
