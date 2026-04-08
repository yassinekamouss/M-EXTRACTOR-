// Apply Vanilla JS camelCase nomenclature rule
document.addEventListener("DOMContentLoaded", () => {
  const uploadForm = document.getElementById("uploadForm");
  const imageInput = document.getElementById("imageInput");
  const extractBtn = document.getElementById("extractBtn");
  const statusMessage = document.getElementById("statusMessage");
  const resultsContainer = document.getElementById("resultsContainer");
  const metadataContent = document.getElementById("metadataContent");
  const mapElement = document.getElementById("map");
  const mapWrapper = document.querySelector(".map-wrapper");
  const noGpsMessage = document.getElementById("noGpsMessage");
  const fileDropArea = document.querySelector(".file-drop-area");

  let leafletMap = null;
  let locationMarker = null;

  const validMimeTypes = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
  ];

  // Fancy upload handling for HUD input
  imageInput.addEventListener("change", (e) => {
    const instruction = document.querySelector(".file-instruction");

    // Reset classes
    instruction.classList.remove("success", "error");
    fileDropArea.classList.remove("success", "error");

    if (e.target.files.length > 0) {
      const file = e.target.files[0];
      const fileType = file.type;
      const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();

      const isValidMime = validMimeTypes.includes(fileType);
      const isFallbackHeic = ext === ".heic" || ext === ".heif";

      if (isValidMime || isFallbackHeic) {
        instruction.textContent = `> FILE LOADED: ${file.name}`;
        instruction.classList.add("success");
        fileDropArea.classList.add("success");
      } else {
        console.warn(
          `[Validation Failed] File Name: ${file.name}, reported MIME Type: ${fileType || "Unknown"}`,
        );
        instruction.textContent = `> UNSUPPORTED FORMAT: ${file.name}`;
        instruction.classList.add("error");
        fileDropArea.classList.add("error");
        // Clear input to prevent submission of invalid file
        imageInput.value = "";
      }
    } else {
      instruction.textContent = `> INITIALIZE UPLOAD SEQUENCE <`;
    }
  });

  // Drag and Drop support
  ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
    fileDropArea.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    fileDropArea.addEventListener(eventName, () => {
      fileDropArea.style.background = "rgba(0, 255, 204, 0.15)";
      fileDropArea.style.boxShadow = "var(--glow-spread)";
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    fileDropArea.addEventListener(eventName, () => {
      fileDropArea.style.background = "rgba(0, 255, 204, 0.03)";
      fileDropArea.style.boxShadow = "none";
    });
  });

  fileDropArea.addEventListener("drop", (e) => {
    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      imageInput.files = droppedFiles;

      // Manually trigger the change event to update the UI
      const event = new Event("change");
      imageInput.dispatchEvent(event);
    }
  });

  uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const selectedFile = imageInput.files[0];
    if (!selectedFile) {
      displayStatus("_[ error: NO_VALID_FILE_DETECTED ]_", "error");
      return;
    }

    const formData = new FormData();
    formData.append("image", selectedFile);

    displayStatus("_[ sys: INITIALIZING_EXTRACTION... ]_", "success");
    resultsContainer.classList.add("hidden");
    extractBtn.disabled = true;
    extractBtn.classList.add("btn-pulsing");
    document.querySelector(".btn-text").textContent = "PARSING DATA...";

    try {
      const apiResponse = await fetch("/extract", {
        method: "POST",
        body: formData,
      });

      // The API Contract guarantees JSON mapping structure
      const jsonPayload = await apiResponse.json();

      if (jsonPayload.status === "success") {
        displayStatus(
          `_[ sys: EXTRACTION_COMPLETE // DATA_READY ]_`,
          "success",
        );
        renderResults(jsonPayload.data);
      } else {
        displayStatus(
          `_[ error: ${jsonPayload.message.toUpperCase()} ]_`,
          "error",
        );
      }
    } catch (apiError) {
      displayStatus("_[ error: CRITICAL_NETWORK_FAILURE ]_", "error");
      console.error(apiError);
    } finally {
      extractBtn.disabled = false;
      extractBtn.classList.remove("btn-pulsing");
      document.querySelector(".btn-text").textContent = "EXECUTE EXTRACTION";
    }
  });

  function displayStatus(messageText, messageType) {
    statusMessage.textContent = messageText;
    statusMessage.className = `status-feed ${messageType}`;
  }

  function typewriterEffect(element, text, speed = 5) {
    element.textContent = "";
    let i = 0;
    element.classList.add("typing");

    function type() {
      if (i < text.length) {
        element.textContent += text.charAt(i);
        i++;
        setTimeout(type, speed);
      } else {
        element.classList.remove("typing");
      }
    }
    type();
  }

  function renderResults(metadataJson) {
    // Show main container
    resultsContainer.classList.remove("hidden");

    // Populate Card
    const visualData = { ...metadataJson };
    const jsonString = JSON.stringify(visualData, null, 2);

    // Execute typewriter effect for the HUD
    typewriterEffect(metadataContent, jsonString);

    // Process GPS
    if (
      metadataJson.gps &&
      metadataJson.gps.lat !== undefined &&
      metadataJson.gps.lng !== undefined
    ) {
      mapWrapper.classList.remove("hidden");
      noGpsMessage.classList.add("hidden");
      updateMap(metadataJson.gps.lat, metadataJson.gps.lng);
    } else {
      mapWrapper.classList.add("hidden");
      noGpsMessage.classList.remove("hidden");

      // Detailed status handling
      let privacyMsg =
        "Privacy Protection Detected: Geospatial tags have been removed from this file header.";
      if (metadataJson.gps_status === "COORDINATES_ZEROED") {
        privacyMsg =
          "Privacy Protection Detected: Coordinates exist but have been explicitly zeroed out.";
      }
      noGpsMessage.innerHTML = `⚠️ <span style="font-size: 0.9em; opacity: 0.8;">${privacyMsg}</span><br><br>[ ${metadataJson.gps_status} ]`;
    }
  }

  function updateMap(latitude, longitude) {
    const coordinateTuple = [latitude, longitude];

    // Setup map initially, otherwise pan existing instance
    if (!leafletMap) {
      leafletMap = L.map("map").setView(coordinateTuple, 14);
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
          maxZoom: 19,
          attribution: "© OpenStreetMap contributors, © CARTO",
        },
      ).addTo(leafletMap);
    } else {
      leafletMap.setView(coordinateTuple, 14);
    }

    // Apply custom Marker styled for HUD
    const hudIcon = L.divIcon({
      className: "hud-marker",
      html: '<div style="background:var(--accent-color); width:15px; height:15px; border-radius:50%; box-shadow:0 0 10px var(--accent-color); border:2px solid #fff;"></div>',
      iconSize: [15, 15],
    });

    if (locationMarker) {
      locationMarker.setLatLng(coordinateTuple);
      locationMarker.setIcon(hudIcon);
    } else {
      locationMarker = L.marker(coordinateTuple, { icon: hudIcon }).addTo(
        leafletMap,
      );
    }

    // Required due to leaflet resizing inside dynamically revealed tags
    setTimeout(() => {
      leafletMap.invalidateSize();
    }, 300);
  }
});
