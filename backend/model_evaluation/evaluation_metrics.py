"""Classification, calibration, error, and precision-recall reporting."""
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score,average_precision_score,balanced_accuracy_score,brier_score_loss,
    classification_report,confusion_matrix,f1_score,log_loss,precision_recall_curve,precision_score,recall_score,
    roc_auc_score)
from sklearn.preprocessing import label_binarize

def expected_calibration_error(y_true,probabilities,labels,bins=10):
    encoded=np.asarray([labels.index(x) for x in y_true]); confidence=probabilities.max(axis=1); prediction=probabilities.argmax(axis=1)
    total=len(y_true); ece=0.0; rows=[]
    edges=np.linspace(0,1,bins+1)
    for lo,hi in zip(edges[:-1],edges[1:]):
        mask=(confidence>=lo)&(confidence<hi if hi<1 else confidence<=hi)
        if not mask.any(): continue
        accuracy=float((prediction[mask]==encoded[mask]).mean()); mean_conf=float(confidence[mask].mean())
        ece+=mask.sum()/total*abs(accuracy-mean_conf); rows.append({"lower":lo,"upper":hi,"samples":int(mask.sum()),"accuracy":accuracy,"mean_confidence":mean_conf})
    return float(ece),rows

def evaluate_predictions(y_true,y_pred,probabilities,labels):
    report=classification_report(y_true,y_pred,labels=labels,output_dict=True,zero_division=0)
    binary=label_binarize(y_true,classes=labels); ece,bins=expected_calibration_error(list(y_true),probabilities,labels)
    per_class={label:{**report[label],"average_precision":float(average_precision_score(binary[:,i],probabilities[:,i])) if binary[:,i].any() else None} for i,label in enumerate(labels)}
    metrics={"samples":len(y_true),"accuracy":float(accuracy_score(y_true,y_pred)),"balanced_accuracy":float(balanced_accuracy_score(y_true,y_pred)),
        "macro_precision":float(precision_score(y_true,y_pred,average="macro",zero_division=0)),"macro_recall":float(recall_score(y_true,y_pred,average="macro",zero_division=0)),
        "macro_f1":float(f1_score(y_true,y_pred,average="macro",zero_division=0)),"weighted_f1":float(f1_score(y_true,y_pred,average="weighted",zero_division=0)),"per_class":per_class,
        "calibration":{"expected_calibration_error_10_bins":ece,"multiclass_log_loss":float(log_loss(y_true,probabilities,labels=labels)),
        "multiclass_brier_score":float(np.mean(np.sum((probabilities-binary)**2,axis=1))),"calibration_bins":bins,"probabilities_calibrated":False}}
    try:
        auc=float(roc_auc_score(binary,probabilities,average="macro",multi_class="ovr")); metrics["macro_roc_auc_ovr"]=auc if np.isfinite(auc) else None
    except ValueError: metrics["macro_roc_auc_ovr"]=None
    return metrics,report,binary

def error_analyses(y_true,y_pred,labels):
    actual=pd.Series(np.asarray(y_true),name="actual"); predicted=pd.Series(np.asarray(y_pred),name="predicted")
    rows=[]
    for label in labels:
        truth=actual.eq(label); pred=predicted.eq(label); fn=truth&~pred; fp=~truth&pred
        rows.append({"fault_class":label,"support":int(truth.sum()),"predicted_count":int(pred.sum()),"false_negatives":int(fn.sum()),
            "false_negative_rate":float(fn.sum()/max(1,truth.sum())),"false_positives":int(fp.sum()),"false_positive_rate":float(fp.sum()/max(1,(~truth).sum())),
            "top_false_negative_prediction":predicted[fn].value_counts().index[0] if fn.any() else "",
            "top_false_positive_actual":actual[fp].value_counts().index[0] if fp.any() else ""})
    return pd.DataFrame(rows)

def precision_recall_rows(binary,probabilities,labels,max_points_per_class=1000):
    frames=[]
    for i,label in enumerate(labels):
        if not binary[:,i].any(): continue
        precision,recall,threshold=precision_recall_curve(binary[:,i],probabilities[:,i])
        if len(threshold)>max_points_per_class:
            keep=np.unique(np.linspace(0,len(threshold)-1,max_points_per_class,dtype=int))
            precision,recall,threshold=precision[keep],recall[keep],threshold[keep]
        else: precision,recall=precision[:-1],recall[:-1]
        frames.append(pd.DataFrame({"fault_class":label,"precision":precision,"recall":recall,"threshold":threshold}))
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=["fault_class","precision","recall","threshold"])
