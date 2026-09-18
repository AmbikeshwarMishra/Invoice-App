// Row Management
function addRow() {
    let table = document.getElementById("itemsTable").getElementsByTagName('tbody')[0];
    let row = table.insertRow();
    row.innerHTML = `
        <td><input type="text" name="product[]" class="form-control" required></td>
        <td><input type="number" name="qty[]" class="form-control qty" value="1" onchange="calculateTotals()"></td>
        <td><input type="number" step="0.01" name="rate[]" class="form-control rate" value="0" onchange="calculateTotals()"></td>
        <td><input type="text" class="form-control gross" value="0.00" readonly></td>
        <td><button type="button" class="btn btn-danger" onclick="removeRow(this)">X</button></td>
    `;
}

function removeRow(btn) {
    let row = btn.parentNode.parentNode;
    row.parentNode.removeChild(row);
    calculateTotals();
}

// Auto Calculation Logic
function calculateTotals() {
    let rows = document.querySelectorAll("#itemsTable tbody tr");
    rows.forEach(row => {
        let qty = parseFloat(row.querySelector('.qty').value) || 0;
        let rate = parseFloat(row.querySelector('.rate').value) || 0;
        row.querySelector('.gross').value = (qty * rate).toFixed(2);
    });
}

// Web Speech API Voice Item Entry Feature
function startVoiceRecognition() {
    if (!('webkitSpeechRecognition' in window)) {
        alert("Voice recognition is not supported in this browser.");
        return;
    }
    let recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.start();

    recognition.onresult = function(event) {
        let speechResult = event.results[0][0].transcript;
        alert("Voice Input Detected: " + speechResult);

        // Example Regex matching Pattern: "Add 2 Monitors at 12000"
        let qtyMatch = speechResult.match(/\d+/);
        if (qtyMatch) {
            addRow();
            let rows = document.querySelectorAll("#itemsTable tbody tr");
            let lastRow = rows[rows.length - 1];
            lastRow.querySelector('input[name="product[]"]').value = speechResult;
        }
    };
}

// OCR File Scanner Handler
function uploadReceipt() {
    let fileInput = document.getElementById('receiptUpload');
    let formData = new FormData();
    formData.append('receipt', fileInput.files[0]);

    fetch('/scan_receipt', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        alert("Extracted Text via OCR:\n" + data.extracted_text);
    });
}