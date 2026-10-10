import type {Frame} from './types';

export default function MLStatus({frame}:{frame:Frame|null}){
  const ml=frame?.mlInference;
  const available=ml?.status==='available';
  return <section className="wt-panel wt-controls">
    <span className="wt-kicker">OPTIONAL ML EVIDENCE</span><h3>Classifier status</h3>
    <p>{available
      ? `Candidate prediction: ${String(ml?.fault_class)}. Uncalibrated model score: ${String(ml?.model_score)}. Model: ${String(ml?.model_version)}. Release gate: ${ml?.release_gate_passed===true?'passed':'failed'}.`
      : `ML inference ${String(ml?.status||'unavailable')}. Engineering rules and statistical diagnostics remain active.`}</p>
    <p>{available
      ? 'This synthetic-data model result is a hypothesis, not a confirmed fault or failure probability.'
      : 'No ML prediction is used in the engineering assessment.'}</p>
  </section>;
}
