(async () => {
    const $ = (id) => document.getElementById(id);

    function scenario() {
        return {
            fault: $("fault")?.value || "none",
            severity: +($("severity")?.value || 0.6),
            altitude_ft: +($("altitude")?.value || 8000),
            ambient_c: +($("ambient")?.value || 35),
            duration_h: +($("duration")?.value || 6),
            rapid_throttle: ($("throttle")?.value || "false") === "true",
            operating_state: $("operating")?.value || "CRUISE"
        };
    }

    function formatValue(value) {
        if (value === null || value === undefined) {
            return "—";
        }

        if (typeof value === "number") {
            return Number.isFinite(value)
                ? value.toFixed(3)
                : "—";
        }

        if (typeof value === "boolean") {
            return value ? "Yes" : "No";
        }

        if (typeof value === "object") {
            return Object.entries(value)
                .map(([key, val]) => {
                    return `${key}: ${formatValue(val)}`;
                })
                .join(" • ");
        }

        return String(value);
    }

    function renderDegradationState(state) {
        if (!state) {
            return "No active degradation";
        }

        if (typeof state !== "object") {
            return String(state);
        }

        const entries = Object.entries(state);

        if (!entries.length) {
            return "No active degradation";
        }

        return entries
            .map(([key, value]) => {
                return `${key}: ${formatValue(value)}`;
            })
            .join(" • ");
    }

    function renderTelemetry() {
        const telemetryTable =
            document.querySelector("#telemetry");

        if (!telemetryTable) {
            return;
        }

        const data =
    window.__aeropulseLiveState ||
    window.__aeropulseLatestAnalysis;

        if (!data || !data.telemetry) {
            return;
        }

        telemetryTable.innerHTML =
            Object.entries(data.telemetry)
                .map(([key, value]) => {

                    let displayValue;

                    if (key === "Degradation_State") {
                        displayValue =
                            renderDegradationState(value);
                    } else {
                        displayValue =
                            formatValue(value);
                    }

                    return `
                        <tr>
                            <td>${key}</td>
                            <td>${displayValue}</td>
                        </tr>
                    `;
                })
                .join("");
    }

    /*
     * Intercept /api/analyze so the dashboard can
     * keep the complete structured telemetry response.
     */
    const originalFetch = window.fetch.bind(window);

    window.fetch = async (...args) => {

        const response =
            await originalFetch(...args);

        try {

            const url = String(args[0]);

            if (url.includes("/api/analyze")) {

                const clone = response.clone();

                clone.json()
                    .then((data) => {

                        window.__aeropulseLatestAnalysis =
                            data;

                        setTimeout(
                            renderTelemetry,
                            0
                        );

                    })
                    .catch(() => {});
            }

        } catch (_) {}

        return response;
    };

    /*
     * Mission What-If + RUL
     */
    function injectWhatIf() {

        if ($("phase6")) {
            return;
        }

        const root =
            document.querySelector(".shell");

        if (!root) {
            return;
        }

        const card =
            document.createElement("div");

        card.id = "phase6";
        card.className = "card";

        card.innerHTML = `
            <h2>Mission What-If + RUL</h2>

            <div class="grid two">

                <div>

                    <p class="tiny">
                        Compare the current mission against
                        an alternative mission profile.
                    </p>

                    <label>
                        Alternative altitude (ft)
                        <input
                            id="wfAlt"
                            type="number"
                            value="25000"
                        >
                    </label>

                    <label>
                        Alternative ambient °C
                        <input
                            id="wfTemp"
                            type="number"
                            value="45"
                        >
                    </label>

                    <label>
                        Alternative duration (h)
                        <input
                            id="wfDur"
                            type="number"
                            value="8"
                        >
                    </label>

                    <label>
                        Alternative rapid throttle

                        <select id="wfThrottle">
                            <option value="false">
                                No
                            </option>

                            <option value="true">
                                Yes
                            </option>
                        </select>
                    </label>

                    <button id="wfRun">
                        Run What-If
                    </button>

                </div>

                <div
                    id="wfResult"
                    class="architecture"
                >
                    No scenario comparison yet.
                </div>

            </div>
        `;

        const replay =
            document.createElement("div");

        replay.id = "replayRulCard";
        replay.className = "card";

        replay.innerHTML = `
            <h2>Replay Health + RUL Trend</h2>

            <canvas
                id="rulTimeline"
                width="900"
                height="260"
            ></canvas>

            <div
                id="rulReplaySummary"
                class="tiny"
            >
                Run Mission Replay to populate the trend.
            </div>
        `;

        const before =
            document.querySelector(".footer");

        if (before) {
            root.insertBefore(card, before);
            root.insertBefore(replay, before);
        } else {
            root.appendChild(card);
            root.appendChild(replay);
        }

        $("wfRun").onclick = runWhatIf;
    }

    async function runWhatIf() {

        const base = scenario();

        const alternative = {
            ...base,

            altitude_ft:
                +$("wfAlt").value,

            ambient_c:
                +$("wfTemp").value,

            duration_h:
                +$("wfDur").value,

            rapid_throttle:
                $("wfThrottle").value === "true"
        };

        try {

            const response =
                await fetch(
                    "/api/mission-whatif-rul",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            baseline: base,
                            alternative
                        })
                    }
                );

            const data =
                await response.json();

            if (!response.ok) {
                throw new Error(
                    JSON.stringify(data.detail)
                );
            }

            const baseline =
                data.baseline;

            const alternativeResult =
                data.alternative;

            const impact =
                data.impact;

            $("wfResult").innerHTML = `
                <b>Baseline RUL:</b>
                ${baseline.rul.rul_hours} h
                <br>

                <b>What-If RUL:</b>
                ${alternativeResult.rul.rul_hours} h
                <br>

                <b>RUL impact:</b>
                ${impact.rul_hours} h
                <br>

                <b>Baseline health:</b>
                ${baseline.health_index}
                <br>

                <b>What-If health:</b>
                ${alternativeResult.health_index}
                <br>

                <b>Degradation impact:</b>
                ${impact.degradation_severity}
            `;

        } catch (error) {

            $("wfResult").textContent =
                "What-If failed: " +
                error.message;
        }
    }

    function drawRul(points) {

        const canvas =
            $("rulTimeline");

        if (!canvas) {
            return;
        }

        const ctx =
            canvas.getContext("2d");

        const W =
            canvas.width;

        const H =
            canvas.height;

        const padding = 38;

        ctx.clearRect(
            0,
            0,
            W,
            H
        );

        ctx.fillStyle =
            "#081424";

        ctx.fillRect(
            0,
            0,
            W,
            H
        );

        if (!points || !points.length) {
            return;
        }

        const max =
            Math.max(
                1,
                ...points.map(
                    point =>
                        point.rul_upper_hours ||
                        point.rul_hours ||
                        0
                )
            );

        const min = 0;

        ctx.strokeStyle =
            "#55d7ff";

        ctx.lineWidth = 2.5;

        ctx.beginPath();

        points.forEach((point, index) => {

            const x =
                padding +
                (W - 2 * padding) *
                index /
                Math.max(
                    1,
                    points.length - 1
                );

            const rul =
                Number(
                    point.rul_hours || 0
                );

            const y =
                H -
                padding -
                (H - 2 * padding) *
                ((rul - min) /
                Math.max(
                    1,
                    max - min
                ));

            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }

        });

        ctx.stroke();

        ctx.fillStyle =
            "#91a5c2";

        ctx.font =
            "12px system-ui";

        ctx.fillText(
            "RUL (hours)",
            padding,
            18
        );

        ctx.fillText(
            "0",
            padding,
            H - 10
        );

        ctx.fillText(
            max.toFixed(1),
            padding,
            30
        );
    }

    /*
     * Mission replay
     */
    window.runReplay = async function () {

        try {

            const s =
                scenario();

            const body = {
                ...s,

                steps: 48,

                step_minutes: 5,

                fault_onset_ratio:
                    +$("onset").value
            };

            const response =
                await fetch(
                    "/api/replay",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify(body)
                    }
                );

            const data =
                await response.json();

            if (!response.ok) {
                throw new Error(
                    JSON.stringify(data.detail)
                );
            }

            drawRul(data.timeline);

            const summary =
                data.summary;

            const rulDemo =
                summary.rul_method_demonstrator;

            if (
                rulDemo &&
                rulDemo.status === "DEGRADING"
            ) {

                $("rul").textContent =
                    fmtRul(
                        summary.final_rul_hours
                    );

                $("rulSub").textContent =
                    `${summary.rul_change_hours >= 0 ? "+" : ""}` +
                    `${summary.rul_change_hours} h over replay • method demo`;

            } else {

                $("rul").textContent =
                    "Stable";

                $("rulSub").textContent =
                    rulDemo?.status ||
                    "STABLE_OR_NON_DEGRADING • method demo";
            }

            $("events").innerHTML = `
                <div class="event">
                    <strong>Fault onset</strong>
                    ${
                        summary.fault_onset_min ??
                        "none"
                    } min
                </div>

                <div class="event">
                    <strong>
                        Hybrid intelligent warning
                    </strong>
                    ${
                        summary.intelligent_warning_min ??
                        0
                    } min
                </div>

                <div class="event">
                    <strong>
                        3σ reference
                    </strong>
                    ${
                        summary.reference_alarm_min ??
                        0
                    } min
                </div>

                <div class="event">
                    <strong>
                        Timing difference
                    </strong>
                    ${
                        summary.rul_change_hours ??
                        0
                    } h
                </div>
            `;

            const last =
                data.timeline[
                    data.timeline.length - 1
                ];

            if (last) {

                if ($("health")) {
                    $("health").textContent =
                        last.health_state ||
                        "—";
                }

                if ($("healthIndex")) {
                    $("healthIndex").textContent =
                        typeof last.health_index === "number"
                            ? last.health_index.toFixed(1)
                            : "—";
                }

                if ($("missionRisk")) {
                    $("missionRisk").textContent =
                        `${last.risk_level || ""} ` +
                        `${typeof last.risk_score === "number"
                            ? last.risk_score.toFixed(0)
                            : "—"}`;
                }

            }

        } catch (error) {

            alert(error.message);

        }
    };

    function fmtRul(value) {

        return typeof value === "number" &&
               Number.isFinite(value)
            ? value.toFixed(1) + " h"
            : "—";
    }

    /*
     * Initial injection
     */
    injectWhatIf();

})();





