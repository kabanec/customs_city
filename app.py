from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import requests
import json
from dotenv import load_dotenv
import os
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for session

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# API endpoints
DOCUMENTS_API_URL = "https://api-cert.customscity.com/api/documents"
SEND_API_URL = "https://api-cert.customscity.com/api/send"
REVIEW_HTS_API_URL = "https://api-cert.customscity.com/api/review-hts"

# Bearer token from .env
BEARER_TOKEN = os.getenv("CUSTOMSCITY_BEARER_TOKEN")

# Headers for API requests
DOCUMENTS_HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {BEARER_TOKEN}"
}

SEND_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {BEARER_TOKEN}"
}

DELETE_HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {BEARER_TOKEN}"
}

VIEW_HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {BEARER_TOKEN}"
}

REVIEW_HTS_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {BEARER_TOKEN}"
}

# Allowed values for sendAs in documents API
VALID_DOCUMENT_SEND_AS = ["add", "replace", "update", "cancel"]

# Configure session with retries
session_requests = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session_requests.mount('https://', HTTPAdapter(max_retries=retries))


@app.route('/')
def index():
    """Render the Type 86 manifest form."""
    return render_template('type86_manifest_form.html')


@app.route('/submit_manifest', methods=['POST'])
def submit_manifest():
    """Handle form submission and send POST request to documents API."""
    try:
        # Extract form data
        form_data = request.form

        # Validate sendAs for documents API
        send_as = form_data.get('sendAs', 'add')
        if send_as not in VALID_DOCUMENT_SEND_AS:
            return jsonify({
                "status": "error",
                "message": f"Invalid sendAs value: {send_as}. Must be one of {VALID_DOCUMENT_SEND_AS}"
            }), 400

        # Log form data
        logger.debug("Form data received: %s", dict(form_data))

        # Construct manifest JSON for documents API
        manifest = {
            "type": form_data.get('type', 'abi-type86'),
            "send": False,
            "sendAs": send_as,
            "version": 2,
            "body": [
                {
                    "dateOfArrival": int(form_data.get('dateOfArrival', '20221013')),
                    "timeOfArrival": form_data.get('timeOfArrival', '0010'),
                    "entryType": form_data.get('entryType', '86'),
                    "modeOfTransport": form_data.get('modeOfTransport', '10'),
                    "IORType": form_data.get('IORType', 'EI'),
                    "IORNumber": form_data.get('IORNumber', '12-1234567XX'),
                    "portOfEntry": form_data.get('portOfEntry', '1102'),
                    "manifestNumber": form_data.get('manifestNumber', 'ABC01'),
                    "filerContactName": form_data.get('filerContactName', 'BTS TXT'),
                    "filerPhoneNumber": int(form_data.get('filerPhoneNumber', '123457890')),
                    "bondType": form_data.get('bondType', '0'),
                    "billType": form_data.get('billType', 'M'),
                    "MBOLNumber": form_data.get('MBOLNumber', 'MBOLBTS0602'),
                    "HBOLNumber": form_data.get('HBOLNumber', 'HBOL12BTS6701'),
                    "equipmentNumber": form_data.get('equipmentNumber', '1234567890'),
                    "vesselName": form_data.get('vesselName', 'Name'),
                    "sellerName": form_data.get('sellerName', 'Test Name Seller'),
                    "sellerAddress1": form_data.get('sellerAddress1', 'Test Address'),
                    "sellerAddress2": None,
                    "sellerCity": form_data.get('sellerCity', 'BEIJING'),
                    "sellerCountry": form_data.get('sellerCountry', 'CN'),
                    "consigneeName": form_data.get('consigneeName', 'Test Name Consignee'),
                    "consigneeIdentifierCode": form_data.get('consigneeIdentifierCode', 'EI'),
                    "consigneeAddress1": form_data.get('consigneeAddress1', 'Test Address'),
                    "consigneeAddress2": None,
                    "consigneeCity": form_data.get('consigneeCity', 'PICKERING'),
                    "consigneePostalCode": form_data.get('consigneePostalCode', '12345'),
                    "consigneeTaxID": form_data.get('consigneeTaxID', '12-123456789'),
                    "consigneeStateOrProvince": form_data.get('consigneeStateOrProvince', 'OH'),
                    "consigneeCountry": form_data.get('consigneeCountry', 'US'),
                    "totalQuantity": int(form_data.get('totalQuantity', '5')),
                    "knownImporter": form_data.get('knownImporter', 'Y'),
                    "perishableGoods": form_data.get('perishableGoods', 'N'),
                    "shipments": [
                        {
                            "description": form_data.get('shipmentDescription', 'TEST BTS'),
                            "HTSNumber": form_data.get('shipmentHTSNumber', '2903992000'),
                            "countryOfOrigin": form_data.get('shipmentCountryOfOrigin', 'CN'),
                            "lineItemValue": form_data.get('shipmentLineItemValue', '750')
                        }
                    ]
                }
            ]
        }

        # Log the documents payload
        logger.debug("Sending documents payload: %s", json.dumps(manifest, indent=2))

        # Send POST request to documents API with timeout
        try:
            documents_response = session_requests.post(
                DOCUMENTS_API_URL,
                headers=DOCUMENTS_HEADERS,
                data=json.dumps(manifest),
                timeout=10
            )
            documents_response.raise_for_status()
            documents_result = documents_response.json()
        except requests.exceptions.ConnectionError as conn_err:
            logger.error("Documents API connection error: %s", conn_err)
            return jsonify({
                "status": "error",
                "message": "Failed to connect to the documents API. The server may be down or unreachable.",
                "api_error": {"detail": str(conn_err)},
                "documents_response": None
            }), 503

        # Store MBOLNumber and HBOLNumber in session
        session['MBOLNumber'] = form_data.get('MBOLNumber', 'MBOLBTS0602')
        session['HBOLNumber'] = form_data.get('HBOLNumber', 'HBOL12BTS6701')

        # Return documents response instead of redirecting
        return jsonify({
            "status": "success",
            "documents_response": documents_result
        })

    except requests.exceptions.RequestException as e:
        error_response = {}
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
            except ValueError:
                error_response = {"message": e.response.text}
        logger.error("Documents API error: %s", e)
        return jsonify({
            "status": "error",
            "message": "Failed to process the request due to a server error.",
            "api_error": error_response or {"detail": str(e)},
            "documents_response": None
        }), 500
    except ValueError as e:
        logger.error("Input error: %s", e)
        return jsonify({
            "status": "error",
            "message": "Invalid input data: " + str(e),
            "documents_response": None
        }), 400


@app.route('/proceed_to_actions', methods=['POST'])
def proceed_to_actions():
    """Redirect to manifest actions page."""
    return jsonify({
        "status": "redirect",
        "redirect_url": url_for('manifest_actions')
    })


@app.route('/review_hts', methods=['POST'])
def review_hts():
    """Verify HTS code using the review-hts API."""
    try:
        data = request.json
        hts_number = data.get('HTSNumber')
        description = data.get('description')
        mbol_number = session.get('MBOLNumber', 'MBOLBTS0602')

        if not hts_number:
            return jsonify({
                "status": "error",
                "message": "HTS Number is required."
            }), 400

        payload = {
            "MBOLNumber": mbol_number,
            "HBOLNumber": None,
            "onlyIssues": False,
            "skip": 0,
            "htsNumbers": [hts_number]
        }

        if description:
            payload["description"] = description

        logger.debug("Sending review-hts payload: %s", json.dumps(payload, indent=2))

        response = session_requests.post(
            REVIEW_HTS_API_URL,
            headers=REVIEW_HTS_HEADERS,
            data=json.dumps(payload),
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        # Check if HTS is valid based on API response
        # Assuming invalid HTS returns issues or errors
        is_valid = not (result.get('issues', []) or result.get('errors', []))
        error_message = result.get('message', 'Invalid HTS code.') if not is_valid else None

        return jsonify({
            "status": "success" if is_valid else "error",
            "message": error_message,
            "response": result
        })

    except requests.exceptions.RequestException as e:
        error_response = {}
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
            except ValueError:
                error_response = {"message": e.response.text}
        logger.error("Review HTS API error: %s", e)
        return jsonify({
            "status": "error",
            "message": error_response.get('message', 'Failed to verify HTS code.'),
            "api_error": error_response or {"detail": str(e)}
        }), 500
    except ValueError as e:
        logger.error("Input error: %s", e)
        return jsonify({
            "status": "error",
            "message": "Invalid input data: " + str(e)
        }), 400


@app.route('/manifest_actions')
def manifest_actions():
    """Render the manifest actions page."""
    mbol_number = session.get('MBOLNumber', 'Unknown')
    return render_template('manifest_actions.html', mbol_number=mbol_number)


@app.route('/delete_manifest', methods=['POST'])
def delete_manifest():
    """Delete a manifest using the documents API."""
    try:
        mbol_number = session.get('MBOLNumber', 'MBOLBTS0602')
        delete_url = f"{DOCUMENTS_API_URL}?type=ABIType86&MBOLNumber={mbol_number}"
        logger.debug("Sending DELETE request to: %s", delete_url)

        response = session_requests.delete(delete_url, headers=DELETE_HEADERS, timeout=10)
        response.raise_for_status()
        result = response.json() if response.content else {"message": "Manifest deleted successfully"}

        return jsonify({
            "status": "success",
            "response": result
        })

    except requests.exceptions.RequestException as e:
        error_response = {}
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
            except ValueError:
                error_response = {"message": e.response.text}
        logger.error("Delete API error: %s", e)
        return jsonify({
            "status": "error",
            "message": "Failed to delete the manifest.",
            "api_error": error_response or {"detail": str(e)}
        }), 500


@app.route('/view_manifest', methods=['POST'])
def view_manifest():
    """View a manifest using the documents API."""
    try:
        mbol_number = session.get('MBOLNumber', 'MBOLBTS0602')
        view_url = f"{DOCUMENTS_API_URL}?type=ABIType86&dateFrom=2025-04-14&dateTo=2025-04-14&masterBOLNumber={mbol_number}&skip=0"
        logger.debug("Sending GET request to: %s", view_url)

        response = session_requests.get(view_url, headers=VIEW_HEADERS, timeout=10)
        response.raise_for_status()
        result = response.json()

        return jsonify({
            "status": "success",
            "response": result
        })

    except requests.exceptions.RequestException as e:
        error_response = {}
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
            except ValueError:
                error_response = {"message": e.response.text}
        logger.error("View API error: %s", e)
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve the manifest.",
            "api_error": error_response or {"detail": str(e)}
        }), 500


@app.route('/send_manifest', methods=['POST'])
def send_manifest():
    """Send a manifest using the send API."""
    try:
        mbol_number = session.get('MBOLNumber', 'MBOLBTS0602')
        hbol_number = session.get('HBOLNumber', 'HBOL12BTS6701')

        if not mbol_number or not hbol_number:
            return jsonify({
                "status": "error",
                "message": "Missing MBOLNumber or HBOLNumber in session."
            }), 400

        send_payload = {
            "type": "abi-type86",
            "sendAs": "add",
            "MBOLNumber": mbol_number,
            "HBOLNumber": [hbol_number],
            "entryNumber": None,
            "sendAllHBOLS": False
        }

        logger.debug("Sending send payload: %s", json.dumps(send_payload, indent=2))

        response = session_requests.post(
            SEND_API_URL,
            headers=SEND_HEADERS,
            data=json.dumps(send_payload),
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        return jsonify({
            "status": "success",
            "response": result
        })

    except requests.exceptions.RequestException as e:
        error_response = {}
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
            except ValueError:
                error_response = {"message": e.response.text}
        logger.error("Send API error: %s", e)
        return jsonify({
            "status": "error",
            "message": "Failed to send the manifest.",
            "api_error": error_response or {"detail": str(e)}
        }), 500


@app.route('/get_manifest', methods=['GET'])
def get_manifest():
    """Handle GET request to retrieve manifest from documents API."""
    try:
        response = session_requests.get(DOCUMENTS_API_URL, headers=DOCUMENTS_HEADERS, timeout=10)
        response.raise_for_status()
        return jsonify({"status": "success", "response": response.json()})

    except requests.exceptions.RequestException as e:
        error_response = {}
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
            except ValueError:
                error_response = {"message": e.response.text}
        logger.error("Get manifest error: %s", e)
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve manifests.",
            "api_error": error_response or {"detail": str(e)}
        }), 500


if __name__ == '__main__':
    app.run(debug=True)