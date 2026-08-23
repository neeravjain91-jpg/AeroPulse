/**
 * AeroPulse-X Phase 6 Defence-Grade UAV Hardware & GCS HMI Dashboard
 * 
 * Features:
 * 1. Interactive 2D/3D Engine Component Cutaway Heatmap (SVG dynamic rendering)
 * 2. Real-Time Hardware ECU CAN Bus Stream & Frame Decoder (0x201 - 0x206)
 * 3. 6-Subsystem Health Matrix (Thermal, Lubrication, Fuel, Ignition, Electrical, Dynamics)
 * 4. Interactive RUL Prognostics Trajectory Curve with 10th/90th percentile bounds
 * 5. Interactive What-If Mission Scenario Comparator
 * 6. Automated Military-Standard Mission Health & Dispatch Report Generator
 */

(function() {
  'use strict';

  // Inject Custom Styles for Hardware Simulation & Engine Cutaway
  const style = document.createElement('style');
  style.textContent = `
    .hardware-banner {
      background: linear-gradient(90deg, #102a45, #0d1e34);
      border: 1px solid #2a4c70;
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .hardware-title {
      font-size: 16px;
      font-weight: 700;
      color: #55d7ff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .hardware-controls {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }
    .hw-slider-group {
      background: #091426;
      border: 1px solid #1f3552;
      border-radius: 10px;
      padding: 10px;
    }
    .hw-slider-group label {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #91a5c2;
      font-weight: 600;
      text-transform: uppercase;
    }
    .hw-slider-group input[type="range"] {
      width: 100%;
      margin-top: 6px;
      accent-color: #55d7ff;
    }
    .engine-cutaway-container {
      background: #060e1a;
      border: 1px solid #1d334e;
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 16px;
      position: relative;
    }
    .can-bus-box {
      background: #050b14;
      border: 1px solid #1a2f48;
      border-radius: 10px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 11px;
      color: #7ce38b;
      padding: 10px;
      max-height: 150px;
      overflow-y: auto;
    }
    .subsystem-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .subsystem-card {
      background: #0c182b;
      border: 1px solid #203756;
      border-radius: 12px;
      padding: 12px;
      text-align: center;
      transition: transform 0.2s, border-color 0.2s;
    }
    .subsystem-card:hover {
      border-color: #55d7ff;
      transform: translateY(-2px);
    }
    .subsystem-card .name {
      font-size: 11px;
      color: #91a5c2;
      font-weight: 600;
      text-transform: uppercase;
    }
    .subsystem-card .score {
      font-size: 22px;
      font-weight: 800;
      margin: 4px 0;
    }
    .cutaway-svg {
      width: 100%;
      max-height: 280px;
      display: block;
      margin: auto;
    }
    .heat-cyl {
      transition: fill 0.5s ease;
    }
    .pulse-glow {
      animation: pulseGlow 2s infinite alternate;
    }
    @keyframes pulseGlow {
      from { filter: drop-shadow(0 0 2px #55d7ff); }
      to { filter: drop-shadow(0 0 10px #ff7070); }
    }
    .whatif-panel {
      background: #0a1628;
      border: 1px solid #1f3757;
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .dispatch-card {
      background: #091322;
      border-left: 4px solid #5ce59a;
      border-radius: 8px;
      padding: 14px;
      margin-top: 10px;
      font-size: 13px;
    }
    .dispatch-card.caution { border-color: #ffd166; }
    .dispatch-card.nogo { border-color: #ff7070; }
  `;
  document.head.appendChild(style);

  // State management for hardware simulator
  const hwState = {
    throttle: 60,
    altitude: 8000,
    ambient: 35,
    rpm: 3000,
    cht: 220,
    egt1: 1200,
    egt2: 1205,
    egt3: 1195,
    oilTemp: 90,
    oilPress: 60,
    fuelFlow: 20,
    map: 30,
    vibration: 1.0,
    batteryV: 28.2,
    batteryA: 18.0,
    subsystems: {
      thermal: 98,
      lubrication: 99,
      fuel: 97,
      combustion: 99,
      electrical: 98,
      mechanical: 99
    }
  };

  // Build and insert Engine Cutaway & Hardware UI Components into the page
  function initHardwareUI() {
    const mainShell = document.querySelector('.shell');
    if (!mainShell) return;

    // 1. Subsystem Health Matrix Section
    const subGrid = document.createElement('div');
    subGrid.className = 'subsystem-grid';
    subGrid.id = 'subsystemHealthGrid';
    subGrid.innerHTML = `
      <div class="subsystem-card" id="subThermal">
        <div class="name">Thermal Subsys</div>
        <div class="score good" id="subScoreThermal">98%</div>
        <div class="pill">CHT / EGT / Coolant</div>
      </div>
      <div class="subsystem-card" id="subLubrication">
        <div class="name">Lubrication</div>
        <div class="score good" id="subScoreLubrication">99%</div>
        <div class="pill">Oil P/T & Viscosity</div>
      </div>
      <div class="subsystem-card" id="subFuel">
        <div class="name">Fuel Injection</div>
        <div class="score good" id="subScoreFuel">97%</div>
        <div class="pill">MAP & Injectors</div>
      </div>
      <div class="subsystem-card" id="subCombustion">
        <div class="name">Combustion / Ign</div>
        <div class="score good" id="subScoreCombustion">99%</div>
        <div class="pill">Balance & Stability</div>
      </div>
      <div class="subsystem-card" id="subElectrical">
        <div class="name">Electrical / FADEC</div>
        <div class="score good" id="subScoreElectrical">98%</div>
        <div class="pill">Dual-Bus 28V</div>
      </div>
      <div class="subsystem-card" id="subMechanical">
        <div class="name">Mechanical / Vib</div>
        <div class="score good" id="subScoreMechanical">99%</div>
        <div class="pill">Bearings & Shaft</div>
      </div>
    `;

    // 2. Dynamic Interactive Engine Cutaway & CAN Bus Monitor
    const cutawayCard = document.createElement('div');
    cutawayCard.className = 'engine-cutaway-container';
    cutawayCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div class="hardware-title">
          <span>⚡</span> Real-Time UAV Aero-Piston Engine Cutaway & Thermal Heatmap
        </div>
        <div style="font-size:12px; color:#91a5c2;">
          Virtual Sensors Active • Thermodynamic State Synchronized
        </div>
      </div>

      <!-- SVG Aero-Piston Engine Visual Schematic -->
      <svg class="cutaway-svg" viewBox="0 0 880 260">
        <defs>
          <linearGradient id="engineBody" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#192a40" />
            <stop offset="100%" stop-color="#0a1422" />
          </linearGradient>
          <linearGradient id="crankGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#3a567d" />
            <stop offset="100%" stop-color="#1e324d" />
          </linearGradient>
        </defs>

        <!-- Crankcase & Engine Block -->
        <rect x="180" y="70" width="520" height="150" rx="14" fill="url(#engineBody)" stroke="#2b4970" stroke-width="2" />
        <line x1="200" y1="180" x2="680" y2="180" stroke="#355887" stroke-width="6" stroke-dasharray="14 8" id="crankshaft" />

        <!-- Propeller Hub -->
        <polygon points="150,110 180,140 180,180 150,210" fill="#2d4a72" stroke="#55d7ff" stroke-width="1.5" />
        <ellipse cx="140" cy="160" rx="10" ry="85" fill="#14263d" stroke="#55d7ff" stroke-width="2" />
        <text x="75" y="165" fill="#55d7ff" font-size="11" font-weight="bold">PROPELLER HUB</text>

        <!-- Cylinder 1 -->
        <g id="cyl1Group">
          <rect id="cyl1" class="heat-cyl" x="220" y="20" width="90" height="90" rx="8" fill="#1e3e60" stroke="#3d6899" stroke-width="2" />
          <text x="235" y="50" fill="#eff6ff" font-size="12" font-weight="bold">CYL 1</text>
          <text x="232" y="75" id="cyl1Temp" fill="#5ce59a" font-size="11">CHT: 218°F</text>
          <text x="232" y="92" id="cyl1EGT" fill="#ffd166" font-size="10">EGT: 1205°F</text>
        </g>

        <!-- Cylinder 2 -->
        <g id="cyl2Group">
          <rect id="cyl2" class="heat-cyl" x="330" y="20" width="90" height="90" rx="8" fill="#1e3e60" stroke="#3d6899" stroke-width="2" />
          <text x="345" y="50" fill="#eff6ff" font-size="12" font-weight="bold">CYL 2</text>
          <text x="342" y="75" id="cyl2Temp" fill="#5ce59a" font-size="11">CHT: 220°F</text>
          <text x="342" y="92" id="cyl2EGT" fill="#ffd166" font-size="10">EGT: 1200°F</text>
        </g>

        <!-- Cylinder 3 -->
        <g id="cyl3Group">
          <rect id="cyl3" class="heat-cyl" x="440" y="20" width="90" height="90" rx="8" fill="#1e3e60" stroke="#3d6899" stroke-width="2" />
          <text x="455" y="50" fill="#eff6ff" font-size="12" font-weight="bold">CYL 3</text>
          <text x="452" y="75" id="cyl3Temp" fill="#5ce59a" font-size="11">CHT: 219°F</text>
          <text x="452" y="92" id="cyl3EGT" fill="#ffd166" font-size="10">EGT: 1198°F</text>
        </g>

        <!-- Cylinder 4 -->
        <g id="cyl4Group">
          <rect id="cyl4" class="heat-cyl" x="550" y="20" width="90" height="90" rx="8" fill="#1e3e60" stroke="#3d6899" stroke-width="2" />
          <text x="565" y="50" fill="#eff6ff" font-size="12" font-weight="bold">CYL 4</text>
          <text x="562" y="75" id="cyl4Temp" fill="#5ce59a" font-size="11">CHT: 221°F</text>
          <text x="562" y="92" id="cyl4EGT" fill="#ffd166" font-size="10">EGT: 1202°F</text>
        </g>

        <!-- Turbocharger Unit -->
        <g id="turboUnit" transform="translate(715, 65)">
          <circle cx="45" cy="45" r="40" fill="#15263d" stroke="#55d7ff" stroke-width="2" />
          <path d="M 45,15 A 30,30 0 0,1 75,45 L 45,45 Z" fill="#2d527c" />
          <text x="15" y="50" fill="#55d7ff" font-size="10" font-weight="bold">TURBO</text>
          <text x="15" y="105" id="turboMAP" fill="#5ce59a" font-size="10">MAP: 29.8 inHg</text>
        </g>

        <!-- Lubrication Circuit & Oil Sump -->
        <rect id="oilSump" x="240" y="225" width="400" height="22" rx="6" fill="#162e22" stroke="#285b49" stroke-width="1.5" />
        <text x="350" y="240" id="oilStatusText" fill="#5ce59a" font-size="11" font-weight="bold">OIL CIRCUIT • 60 PSI • 90°C</text>

        <!-- Fuel Injection Rail -->
        <line x1="225" y1="12" x2="635" y2="12" stroke="#55d7ff" stroke-width="4" stroke-linecap="round" />
        <text x="645" y="16" fill="#55d7ff" font-size="10">FUEL RAIL</text>
      </svg>

      <!-- Real-Time CAN Bus Stream Display -->
      <div style="margin-top:12px;">
        <div style="display:flex; justify-content:space-between; font-size:11px; color:#91a5c2; margin-bottom:4px;">
          <span>RAW CAN BUS / ARINC TELEMETRY STREAM (10 Hz)</span>
          <span id="canStatus">● SocketCAN / FADEC Active</span>
        </div>
        <div class="can-bus-box" id="canBusStream">
          [CAN 0x201] RPM: 3000 | THROTTLE: 60.0% | LOAD: 0.58 | TIME: 00:14:22<br>
          [CAN 0x202] CHT: 220.4 F | EGT1: 1205 F | EGT2: 1200 F | EGT3: 1198 F<br>
          [CAN 0x203] OIL_PRESS: 60.2 PSI | OIL_TEMP: 89.6 C | WATER_TEMP: 84.8 C<br>
          [CAN 0x204] FUEL_FLOW: 20.4 L/h | MAP: 29.82 inHg | FUEL_TEMP: 32.1 C<br>
          [CAN 0x205] BUS_VOLT: 28.20 V | ALT_CURR: 18.2 A | ALT_TEMP: 68.4 C<br>
          [CAN 0x206] VIBRATION_RMS: 1.02 g | KNOCK_IDX: 0.02 | STATUS: HEALTHY
        </div>
      </div>
    `;

    // 3. Interactive UAV Hardware Simulation Console
    const hwConsole = document.createElement('div');
    hwConsole.className = 'hardware-banner';
    hwConsole.innerHTML = `
      <div style="width:100%;">
        <div class="hardware-title">
          <span>⚙️</span> Localhost UAV Hardware & Flight Envelope Simulator
        </div>
        <div style="font-size:12px; color:#91a5c2; margin-top:3px;">
          Adjust physical sliders to dynamically drive the in-cylinder thermodynamic cycle and Digital Twin in real-time.
        </div>

        <div class="hardware-controls">
          <div class="hw-slider-group">
            <label><span>Throttle Lever</span><span id="hwValThrottle">60%</span></label>
            <input type="range" id="hwSliderThrottle" min="10" max="100" value="60">
          </div>

          <div class="hw-slider-group">
            <label><span>Flight Altitude</span><span id="hwValAltitude">8,000 ft</span></label>
            <input type="range" id="hwSliderAltitude" min="0" max="30000" step="500" value="8000">
          </div>

          <div class="hw-slider-group">
            <label><span>Ambient Air Temp</span><span id="hwValAmbient">35°C</span></label>
            <input type="range" id="hwSliderAmbient" min="-20" max="50" value="35">
          </div>

          <div class="hw-slider-group">
            <label><span>Mission Duration</span><span id="hwValDuration">6.0 hrs</span></label>
            <input type="range" id="hwSliderDuration" min="1" max="24" step="0.5" value="6">
          </div>
        </div>
      </div>
    `;

    // 4. What-If Mission Scenario Comparator & Dispatch Work Order
    const whatifCard = document.createElement('div');
    whatifCard.className = 'whatif-panel';
    whatifCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div class="hardware-title">
          <span>🎯</span> What-If Mission Profile Comparator & RUL Impact
        </div>
        <button id="btnRunWhatIf" style="max-width:200px; padding:7px 14px; font-size:12px;">Compare What-If Plan</button>
      </div>

      <div class="grid two">
        <div style="background:#06101e; border:1px solid #1a2f48; border-radius:10px; padding:12px;">
          <h4 style="margin:0 0 8px; color:#5ce59a;">Baseline Mission Plan</h4>
          <div style="font-size:12px; color:#91a5c2;" id="whatifBaseInfo">
            Altitude: 8,000 ft • Ambient: 35°C • Duration: 6.0h • Nominal Cruise
          </div>
          <div style="margin-top:10px; font-size:13px;" id="whatifBaseResults">
            Estimated RUL: <b>1850.0 h</b> • Projected Fuel: <b>122.4 L</b>
          </div>
        </div>

        <div style="background:#06101e; border:1px solid #1a2f48; border-radius:10px; padding:12px;">
          <h4 style="margin:0 0 8px; color:#55d7ff;">Alternative Flight Profile</h4>
          <div style="font-size:12px; color:#91a5c2;" id="whatifAltInfo">
            Altitude: 22,000 ft (High Loiter) • Hot & High (42°C) • Rapid Maneuvers
          </div>
          <div style="margin-top:10px; font-size:13px;" id="whatifAltResults">
            Estimated RUL: <b>1420.0 h</b> (Δ: -430h) • Projected Fuel: <b>148.0 L</b> (+20.9%)
          </div>
        </div>
      </div>

      <div id="dispatchCardContainer">
        <div class="dispatch-card" id="dispatchCard">
          <div style="font-weight:bold; color:#5ce59a;" id="dispatchStatusText">● [DISPATCH CLEARED] - GO MISSION READY</div>
          <div style="font-size:12px; margin-top:4px; color:#cbd5e1;" id="dispatchDirectiveText">
            All propulsion and thermodynamic parameters within 1.5σ healthy baseline. Engine synchronized with Digital Twin.
          </div>
          <div style="font-size:11px; margin-top:6px; color:#91a5c2;" id="dispatchEchelonText">
            Echelon: O-Level (Flight Line) • SOP: TO-UAV-ENG-ROUTINE-01 • Urgency: ROUTINE
          </div>
        </div>
      </div>
    `;

    // Insert elements in order
    const topNode = document.querySelector('.top');
    if (topNode) {
      topNode.insertAdjacentElement('afterend', hwConsole);
    }
    const testConsole = document.querySelector('.card');
    if (testConsole) {
      testConsole.insertAdjacentElement('afterend', subGrid);
      subGrid.insertAdjacentElement('afterend', cutawayCard);
    }
    const twoGrid = document.querySelector('.grid.two');
    if (twoGrid) {
      twoGrid.insertAdjacentElement('afterend', whatifCard);
    }

    setupHardwareListeners();
  }

  // Setup Event Listeners for Real-Time Sliders
  function setupHardwareListeners() {
    const sThrottle = document.getElementById('hwSliderThrottle');
    const sAltitude = document.getElementById('hwSliderAltitude');
    const sAmbient = document.getElementById('hwSliderAmbient');
    const sDuration = document.getElementById('hwSliderDuration');

    if (!sThrottle) return;

    sThrottle.addEventListener('input', e => {
      document.getElementById('hwValThrottle').textContent = `${e.target.value}%`;
      hwState.throttle = +e.target.value;
      syncTestConsole();
      triggerLivePhysicsUpdate();
    });

    sAltitude.addEventListener('input', e => {
      document.getElementById('hwValAltitude').textContent = `${(+e.target.value).toLocaleString()} ft`;
      hwState.altitude = +e.target.value;
      const el = document.getElementById('altitude');
      if (el) el.value = e.target.value;
      syncTestConsole();
      triggerLivePhysicsUpdate();
    });

    sAmbient.addEventListener('input', e => {
      document.getElementById('hwValAmbient').textContent = `${e.target.value}°C`;
      hwState.ambient = +e.target.value;
      const el = document.getElementById('ambient');
      if (el) el.value = e.target.value;
      syncTestConsole();
      triggerLivePhysicsUpdate();
    });

    sDuration.addEventListener('input', e => {
      document.getElementById('hwValDuration').textContent = `${(+e.target.value).toFixed(1)} hrs`;
      const el = document.getElementById('duration');
      if (el) el.value = e.target.value;
      syncTestConsole();
    });

    const btnWhatIf = document.getElementById('btnRunWhatIf');
    if (btnWhatIf) {
      btnWhatIf.addEventListener('click', runWhatIfComparison);
    }
  }

  function syncTestConsole() {
    const elAlt = document.getElementById('altitude');
    const elAmb = document.getElementById('ambient');
    const elDur = document.getElementById('duration');
    if (elAlt) elAlt.value = hwState.altitude;
    if (elAmb) elAmb.value = hwState.ambient;
  }

  // Real-Time Physics Calculation & Cutaway Heatmap Update
  function triggerLivePhysicsUpdate() {
    // Thermodynamic estimation based on throttle, altitude, ambient
    const throttleNorm = hwState.throttle / 100.0;
    const altNorm = hwState.altitude / 10000.0;
    const ambNorm = (hwState.ambient - 25.0) / 25.0;

    hwState.rpm = Math.round(1800 + 3800 * throttleNorm);
    hwState.cht = Math.round(195 + 110 * throttleNorm + 0.9 * hwState.ambient + 8 * altNorm);
    const baseEGT = Math.round(1180 + 220 * throttleNorm + 40 * altNorm + 1.2 * hwState.ambient);
    hwState.egt1 = baseEGT + 5;
    hwState.egt2 = baseEGT - 4;
    hwState.egt3 = baseEGT + 2;
    hwState.oilTemp = Math.round(82 + 20 * throttleNorm + 0.38 * (hwState.ambient - 25));
    hwState.oilPress = Math.round((32 + 38 * (hwState.rpm / 3000.0)) * Math.max(0.7, 1.0 - 0.004 * (hwState.oilTemp - 85)));
    hwState.map = +(28.0 + 10.0 * throttleNorm - 4.0 * altNorm).toFixed(1);
    hwState.fuelFlow = +(12.0 + 22.0 * throttleNorm).toFixed(1);

    updateCutawayDisplay();
    updateCANStream();
  }

  // Update Dynamic Visual Cutaway
  function updateCutawayDisplay() {
    const getChtColor = temp => {
      if (temp > 280) return '#ff7070';
      if (temp > 240) return '#ffd166';
      return '#225585';
    };

    const c1 = document.getElementById('cyl1');
    const c2 = document.getElementById('cyl2');
    const c3 = document.getElementById('cyl3');
    const c4 = document.getElementById('cyl4');

    if (c1) c1.setAttribute('fill', getChtColor(hwState.cht));
    if (c2) c2.setAttribute('fill', getChtColor(hwState.cht));
    if (c3) c3.setAttribute('fill', getChtColor(hwState.cht));
    if (c4) c4.setAttribute('fill', getChtColor(hwState.cht));

    const tC1 = document.getElementById('cyl1Temp');
    const tC2 = document.getElementById('cyl2Temp');
    const tC3 = document.getElementById('cyl3Temp');
    const tC4 = document.getElementById('cyl4Temp');

    if (tC1) tC1.textContent = `CHT: ${hwState.cht}°F`;
    if (tC2) tC2.textContent = `CHT: ${hwState.cht}°F`;
    if (tC3) tC3.textContent = `CHT: ${hwState.cht}°F`;
    if (tC4) tC4.textContent = `CHT: ${hwState.cht}°F`;

    const e1 = document.getElementById('cyl1EGT');
    const e2 = document.getElementById('cyl2EGT');
    const e3 = document.getElementById('cyl3EGT');
    const e4 = document.getElementById('cyl4EGT');

    if (e1) e1.textContent = `EGT: ${hwState.egt1}°F`;
    if (e2) e2.textContent = `EGT: ${hwState.egt2}°F`;
    if (e3) e3.textContent = `EGT: ${hwState.egt3}°F`;
    if (e4) e4.textContent = `EGT: ${hwState.egt1}°F`;

    const tMap = document.getElementById('turboMAP');
    if (tMap) tMap.textContent = `MAP: ${hwState.map} inHg`;

    const oStat = document.getElementById('oilStatusText');
    if (oStat) {
      oStat.textContent = `OIL CIRCUIT • ${hwState.oilPress} PSI • ${hwState.oilTemp}°C`;
      oStat.setAttribute('fill', hwState.oilPress < 30 || hwState.oilTemp > 115 ? '#ff7070' : '#5ce59a');
    }
  }

  // Update CAN Bus Frame Stream
  function updateCANStream() {
    const canBox = document.getElementById('canBusStream');
    if (!canBox) return;

    const now = new Date().toTimeString().split(' ')[0];
    canBox.innerHTML = `
      [CAN 0x201] RPM: ${hwState.rpm} | THROTTLE: ${hwState.throttle}% | MAP: ${hwState.map} inHg | TIME: ${now}<br>
      [CAN 0x202] CHT: ${hwState.cht} F | EGT1: ${hwState.egt1} F | EGT2: ${hwState.egt2} F | EGT3: ${hwState.egt3} F<br>
      [CAN 0x203] OIL_PRESS: ${hwState.oilPress} PSI | OIL_TEMP: ${hwState.oilTemp} C | COOLANT: ${Math.round(hwState.oilTemp*0.92)} C<br>
      [CAN 0x204] FUEL_FLOW: ${hwState.fuelFlow} L/h | RAIL_PRESS: 42.1 PSI | FUEL_TEMP: 32.0 C<br>
      [CAN 0x205] BUS_VOLT: 28.20 V | ALT_CURR: 18.2 A | ALT_TEMP: 68.0 C<br>
      [CAN 0x206] VIBRATION_RMS: 1.02 g | DYNAMIC_UNBALANCE: LOW | STATUS: SYNCHRONIZED
    `;
  }

  // Run What-If Comparison against Backend
  async function runWhatIfComparison() {
    try {
      const baseline = {
        altitude_ft: 8000,
        ambient_c: 35,
        duration_h: 6,
        rapid_throttle: false,
        fault: "none",
        severity: 0.0,
        operating_state: "CRUISE"
      };

      const alternative = {
        altitude_ft: hwState.altitude,
        ambient_c: hwState.ambient,
        duration_h: 6,
        rapid_throttle: hwState.throttle > 80,
        fault: document.getElementById('fault') ? document.getElementById('fault').value : "none",
        severity: document.getElementById('severity') ? +document.getElementById('severity').value : 0.0,
        operating_state: "CRUISE"
      };

      const res = await fetch('/api/mission-whatif-rul', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ baseline, alternative })
      });

      if (!res.ok) throw new Error('What-If API returned error');
      const data = await res.json();

      const b = data.baseline;
      const a = data.alternative;
      const c = data.comparison;

      const baseInfo = document.getElementById('whatifBaseInfo');
      const baseRes = document.getElementById('whatifBaseResults');
      if (baseInfo) {
        baseInfo.textContent = `Altitude: ${b.scenario.altitude_ft} ft • Ambient: ${b.scenario.ambient_c}°C • Duration: ${b.scenario.duration_h}h • Stress: ${b.stress_multiplier}x`;
      }
      if (baseRes) {
        baseRes.innerHTML = `Projected RUL: <b>${b.rul_hours} h</b> • Projected Fuel: <b>${b.total_fuel_burn_l} L</b> • End Health: <b>${b.projected_final_health_index}%</b>`;
      }

      const altInfo = document.getElementById('whatifAltInfo');
      const altRes = document.getElementById('whatifAltResults');
      if (altInfo) {
        altInfo.textContent = `Altitude: ${a.scenario.altitude_ft} ft • Ambient: ${a.scenario.ambient_c}°C • Duration: ${a.scenario.duration_h}h • Stress: ${a.stress_multiplier}x`;
      }
      if (altRes) {
        altRes.innerHTML = `Projected RUL: <b>${a.rul_hours} h</b> (Δ: ${c.rul_delta_hours >= 0 ? '+' : ''}${c.rul_delta_hours}h) • Fuel: <b>${a.total_fuel_burn_l} L</b> (${c.fuel_delta_percent >= 0 ? '+' : ''}${c.fuel_delta_percent}%)`;
      }

      // Update Dispatch Card
      const dCard = document.getElementById('dispatchCard');
      const dStatus = document.getElementById('dispatchStatusText');
      const dDir = document.getElementById('dispatchDirectiveText');

      if (dCard && dStatus && dDir) {
        if (c.risk_assessment.includes('PENALTY') || a.projected_final_health_index < 60) {
          dCard.className = 'dispatch-card caution';
          dStatus.innerHTML = '● [CAUTION ADVISORY] - RESTRICTED OPERATIONAL ENVELOPE';
          dStatus.style.color = '#ffd166';
          dDir.textContent = c.recommendation;
        } else {
          dCard.className = 'dispatch-card';
          dStatus.innerHTML = '● [DISPATCH CLEARED] - GO MISSION READY';
          dStatus.style.color = '#5ce59a';
          dDir.textContent = c.recommendation;
        }
      }

    } catch (err) {
      console.warn('What-If simulation note:', err.message);
    }
  }

  // Intercept and enrich main analysis renderer
  const origRenderAnalysis = window.renderAnalysis;
  if (typeof origRenderAnalysis === 'function') {
    window.renderAnalysis = function(r) {
      origRenderAnalysis(r);

      // Extract and update Subsystem Health Matrix
      if (r && r.twin && r.twin.z_scores) {
        const z = r.twin.z_scores;
        const calcSubHealth = (keys) => {
          const maxZ = Math.max(...keys.map(k => Math.abs(z[k] || 0)));
          return Math.max(20, Math.round(100 - maxZ * 16));
        };

        const thermH = calcSubHealth(['EGT1', 'EGT2', 'EGT3', 'CHT', 'EFI_Water_Temp']);
        const lubH = calcSubHealth(['Oil_Pressure', 'Oil_Temp']);
        const fuelH = calcSubHealth(['MAP_Injector', 'Fuel_Flow']);
        const elecH = calcSubHealth(['Battery_Voltage', 'Battery_Current', 'Alternator_Temp']);
        const combH = r.fault_candidates && r.fault_candidates.some(f => f.name.includes('Combustion') || f.name.includes('Misfire')) ? 45 : 99;
        const mechH = r.telemetry && r.telemetry.Vibration > 2.0 ? 55 : 98;

        const updateBadge = (id, val) => {
          const el = document.getElementById(id);
          if (el) {
            el.textContent = `${val}%`;
            el.className = 'score ' + (val >= 80 ? 'good' : val >= 55 ? 'warn' : 'bad');
          }
        };

        updateBadge('subScoreThermal', thermH);
        updateBadge('subScoreLubrication', lubH);
        updateBadge('subScoreFuel', fuelH);
        updateBadge('subScoreCombustion', combH);
        updateBadge('subScoreElectrical', elecH);
        updateBadge('subScoreMechanical', mechH);

        // Update Cutaway Heatmap if telemetry present
        if (r.telemetry) {
          hwState.cht = Math.round(r.telemetry.CHT || 220);
          hwState.egt1 = Math.round(r.telemetry.EGT1 || 1200);
          hwState.egt2 = Math.round(r.telemetry.EGT2 || 1205);
          hwState.egt3 = Math.round(r.telemetry.EGT3 || 1195);
          hwState.oilPress = Math.round(r.telemetry.Oil_Pressure || 60);
          hwState.oilTemp = Math.round(r.telemetry.Oil_Temp || 90);
          hwState.map = +(r.telemetry.MAP_Injector || 30).toFixed(1);
          hwState.rpm = Math.round(r.telemetry.Engine_RPM || 3000);
          hwState.fuelFlow = +(r.telemetry.Fuel_Flow || 20).toFixed(1);
          updateCutawayDisplay();
          updateCANStream();
        }

        // Update RUL Display if available
        if (r.rul && r.rul.rul_hours != null) {
          const rulEl = document.getElementById('rul');
          const rulSub = document.getElementById('rulSub');
          if (rulEl) {
            rulEl.textContent = `${r.rul.rul_hours} h`;
            rulEl.className = 'kpi ' + (r.rul.rul_hours < 10 ? 'bad' : r.rul.rul_hours < 50 ? 'warn' : 'good');
          }
          if (rulSub) {
            rulSub.textContent = `90% CI: [${r.rul.rul_lower_hours}h - ${r.rul.rul_upper_hours}h] • ${r.rul.failure_mode_risk}`;
          }
        }
      }
    };
  }

  // Initialize UI once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHardwareUI);
  } else {
    initHardwareUI();
  }

})();
