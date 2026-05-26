import pandas as pd

def get_selected_frames_forces():
    """
    Connects to an active SAP2000 instance, finds selected frame elements,
    and retrieves their internal forces.
    Returns a pandas DataFrame matching the CSV format:
    ['Frame', 'Station', 'OutputCase', 'StepType', 'P', 'V2', 'V3', 'T', 'M2', 'M3']
    """
    try:
        import comtypes.client
    except ImportError:
        raise Exception("The 'comtypes' package is required for SAP2000 Live API. Please run: pip install comtypes")

    try:
        mySapObject = comtypes.client.GetActiveObject("CSI.SAP2000.API.SapObject")
    except Exception as e:
        raise Exception("Could not connect to active SAP2000 instance. Ensure SAP2000 is open. Error: " + str(e))

    SapModel = mySapObject.SapModel
    
    # Check if model is unlocked (which means no results)
    if not SapModel.GetModelIsLocked():
        raise Exception("SAP2000 model is not locked. Please run the analysis first to get results.")

    # Get selected objects
    ret = SapModel.SelectObj.GetSelected()
    if ret[0] == 0:
        raise Exception("No objects selected in SAP2000. Please select at least one frame.")
    
    number_items = ret[0]
    object_types = ret[1]
    object_names = ret[2]

    # Filter for frames (type 2)
    selected_frames = [name for t, name in zip(object_types, object_names) if t == 2]

    if not selected_frames:
        raise Exception("No frames selected. Please select a frame (line object) in SAP2000.")

    all_results = []
    
    for frame in selected_frames:
        # ItemTypeElm = 0 (Object)
        ret = SapModel.Results.FrameForce(frame, 0)
        num_results = ret[0]
        
        if num_results == 0:
            continue
            
        obj_arr = ret[1]
        obj_sta_arr = ret[2]
        elm_arr = ret[3]
        elm_sta_arr = ret[4]
        load_case_arr = ret[5]
        step_type_arr = ret[6]
        step_num_arr = ret[7]
        p_arr = ret[8]
        v2_arr = ret[9]
        v3_arr = ret[10]
        t_arr = ret[11]
        m2_arr = ret[12]
        m3_arr = ret[13]

        # Convert to SI if necessary, but assume the user handles units or we assume kN, m.
        # Ideally, we retrieve the current units, but we assume the model output is in kN, m 
        # or we rely on the CSV convention.
        
        for i in range(num_results):
            all_results.append({
                "Frame": obj_arr[i],
                "Station": obj_sta_arr[i],
                "OutputCase": load_case_arr[i],
                "StepType": step_type_arr[i],
                "P": p_arr[i],
                "V2": v2_arr[i],
                "V3": v3_arr[i],
                "T": t_arr[i],
                "M2": m2_arr[i],
                "M3": m3_arr[i]
            })

    if not all_results:
        raise Exception("Failed to retrieve forces for the selected frames. Are there active combinations selected for output?")

    df = pd.DataFrame(all_results)
    return df
