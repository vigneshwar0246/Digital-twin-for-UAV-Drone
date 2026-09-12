import {navigate} from './Root';
import './why-it-matters.css';

const challenges = [
  ['Late warnings', 'Threshold alarms react after a value becomes abnormal.'],
  ['Hidden degradation', 'Cooling, lubrication, combustion and sensor issues can develop gradually.'],
  ['No forward view', 'Conventional displays do not estimate future faults or Remaining Useful Life.'],
];
const workflow = [
  ['01', 'Sense', 'Collect live or simulated engine telemetry.'],
  ['02', 'Understand', 'Combine signals with physics and operating context.'],
  ['03', 'Predict', 'Detect anomalies, degradation and probable faults.'],
  ['04', 'Act', 'Support mission and maintenance decisions.'],
];
const capabilities = [
  ['Live engine monitoring', 'Implemented'], ['Subsystem health and trends', 'Implemented'],
  ['Mission simulation and replay', 'Implemented'], ['Explainable fault indicators', 'Implemented'],
  ['Anomaly and fault prediction', 'Prototype'], ['Remaining Useful Life estimate', 'Prototype'],
  ['Maintenance recommendations', 'Prototype'], ['CAN, ECU and edge deployment', 'Planned'],
];
const stages = [
  ['Now', 'Software demonstrator', 'Synthetic data, simulation, dashboards and model validation.'],
  ['Next', 'Test-rig integration', 'Real sensors, CAN ingestion and calibrated engine models.'],
  ['Later', 'Operational deployment', 'Secure edge inference, GCS integration and fleet intelligence.'],
];

export default function WhyItMatters() {
  const scroll = (id: string) => document.getElementById(id)?.scrollIntoView({behavior: 'smooth', block: 'start'});
  return <article className="wim-page">
    <section className="wim-hero" aria-labelledby="wim-title">
      <div className="wim-hero-copy"><span className="wim-kicker">AERO-ENGINE DIGITAL TWIN</span><h1 id="wim-title">See engine risk before it becomes an alarm.</h1><p>Long-endurance UAV missions need more than separate gauges and fixed limits. AERION turns engine telemetry into a synchronized view of current health, developing faults and future maintenance needs.</p><div className="wim-actions"><button className="primary" onClick={() => scroll('how-it-works')}>How it works</button><button onClick={() => navigate('/twin')}>Open the live twin</button></div></div>
      <div className="wim-hero-summary" aria-label="Digital twin value summary"><span>THE SHIFT</span><div><small>FROM</small><strong>“A parameter is abnormal now.”</strong></div><div className="highlight"><small>TO</small><strong>“Health is degrading—here is why, what may happen next and what to inspect.”</strong></div></div>
    </section>
    <section className="wim-section"><header className="wim-section-title"><span>THE PROBLEM</span><h2>Engine data is useful only when it leads to an earlier decision.</h2></header><div className="wim-grid three">{challenges.map(([title, body], index) => <article className="wim-card" key={title}><b>0{index + 1}</b><h3>{title}</h3><p>{body}</p></article>)}</div></section>
    <section className="wim-section" id="how-it-works"><header className="wim-section-title"><span>HOW IT WORKS</span><h2>One clear path from signal to action.</h2><p>RPM, temperature, pressure, fuel, vibration and electrical signals are evaluated together—not as isolated readings.</p></header><div className="wim-workflow">{workflow.map(([number, title, body]) => <article key={title}><b>{number}</b><div><h3>{title}</h3><p>{body}</p></div></article>)}</div></section>
    <section className="wim-section"><header className="wim-section-title"><span>VERIFIED SCOPE</span><h2>What the prototype demonstrates today.</h2><p>Status labels describe evidence in this repository. They do not imply flight validation or manufacturer-approved limits.</p></header><div className="wim-capabilities">{capabilities.map(([name, status]) => <div key={name}><span>{name}</span><b className={`wim-status ${status.toLowerCase()}`}>{status}</b></div>)}</div></section>
    <section className="wim-section"><header className="wim-section-title"><span>DELIVERY PATH</span><h2>Prototype now. Real-engine validation next.</h2></header><div className="wim-stages">{stages.map(([label, title, body], index) => <article className={index === 0 ? 'current' : ''} key={title}><span>{label}</span><h3>{title}</h3><p>{body}</p></article>)}</div></section>
    <section className="wim-final"><span>WHY IT MATTERS</span><h2>Understand the engine now. Predict what may happen next. Act before degradation becomes critical.</h2><button onClick={() => navigate('/twin')}>Explore the live digital twin →</button></section>
  </article>;
}
