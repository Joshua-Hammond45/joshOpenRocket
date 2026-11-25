Attribute VB_Name = "Ork2SW"
'===============================================================================
' Ork2SW - build a member's rocket from the club master template.
'
' One-time setup (Josh / whoever maintains the template):
'   1. SolidWorks > Tools > Macro > New..., save as Ork2SW.swp
'   2. In the VBA editor: File > Import File... > this Ork2SW.bas
'      (delete the empty default module), then set TEMPLATE_ASM below.
'   3. Tools > References: make sure "SldWorks <year> Type Library" and
'      "SolidWorks <year> Constant type library" are checked.
'   4. Put Ork2SW.swp on the club drive / a toolbar button.
'
' Member workflow:
'   python -m ork2sw MyRocket.ork        (writes MyRocket_sw\rocket_params.txt)
'   SolidWorks > Tools > Macro > Run > Ork2SW.swp > pick rocket_params.txt
'
' What it does:
'   - Pack and Go copies the master template into a NEW folder (never edits the
'     master, never moves/renames files afterwards).
'   - Writes every "name"= value line into matching global variables in the
'     assembly and every part that has that global variable.
'   - Switches the assembly to configuration SINGLE or BREAK (middleBreak).
'   - Rebuilds and saves everything.
'===============================================================================
Option Explicit

' >>> Set this to the master template assembly on the club drive <<<
Const TEMPLATE_ASM As String = "C:\HPR\Ork2SW_Template\L1_Rocket.SLDASM"

Const CFG_SINGLE As String = "SINGLE"
Const CFG_BREAK As String = "BREAK"

Dim swApp As SldWorks.SldWorks
Dim gNames As Collection   ' parameter names, in file order
Dim gValues As Collection  ' keyed by name -> value text (e.g. "3.1in")
Dim gLog As String

Sub main()
    Set swApp = Application.SldWorks
    gLog = ""

    Dim paramsPath As String
    paramsPath = swApp.GetOpenFileName("Pick rocket_params.txt from ork2sw", "", _
        "ork2sw parameters (*.txt)|*.txt|", 0, "", "")
    If paramsPath = "" Then Exit Sub
    If Not ReadParams(paramsPath) Then Exit Sub

    If Dir(TEMPLATE_ASM) = "" Then
        swApp.SendMsgToUser2 "Template not found:" & vbCrLf & TEMPLATE_ASM & vbCrLf & _
            "Edit TEMPLATE_ASM at the top of the macro.", swMbStop, swMbOk
        Exit Sub
    End If

    ' New project folder next to the params folder: <params folder>\CAD
    Dim destDir As String
    destDir = Left(paramsPath, InStrRev(paramsPath, "\")) & "CAD\"
    If Dir(destDir, vbDirectory) <> "" Then
        If Dir(destDir & "*.SLDASM") <> "" Then
            If swApp.SendMsgToUser2("A CAD folder already exists here:" & vbCrLf & destDir & vbCrLf & _
                "Overwrite it with a fresh copy of the template?", swMbWarning, swMbYesNo) <> swMbHitYes Then Exit Sub
        End If
    Else
        MkDir destDir
    End If

    Dim newAsm As String
    newAsm = PackAndGoTemplate(destDir)
    If newAsm = "" Then Exit Sub

    Dim errs As Long, warns As Long
    Dim asm As SldWorks.ModelDoc2
    Set asm = swApp.OpenDoc6(newAsm, swDocASSEMBLY, swOpenDocOptions_Silent, "", errs, warns)
    If asm Is Nothing Then
        swApp.SendMsgToUser2 "Could not open the copied assembly: " & newAsm, swMbStop, swMbOk
        Exit Sub
    End If

    ' 1) configuration for the middle break
    Dim cfg As String
    If Val(ParamValue("middleBreak")) >= 1 Then cfg = CFG_BREAK Else cfg = CFG_SINGLE
    If Not asm.ShowConfiguration2(cfg) Then
        Log "!! Assembly has no configuration named " & cfg
    Else
        Log "Configuration: " & cfg
    End If

    ' 2) global variables in the assembly and every referenced part
    Dim used As New Collection
    SetGlobals asm, used
    Dim comps As Variant, i As Long, seen As New Collection, p As String
    comps = asm.GetComponents(False)
    If Not IsEmpty(comps) Then
        For i = 0 To UBound(comps)
            Dim c As SldWorks.Component2
            Set c = comps(i)
            p = c.GetPathName
            If p <> "" And Not InCollection(seen, LCase(p)) Then
                seen.Add LCase(p), LCase(p)
                Dim m As SldWorks.ModelDoc2
                Set m = c.GetModelDoc2
                If m Is Nothing Then  ' suppressed in this configuration: open it directly
                    Set m = swApp.OpenDoc6(p, swDocPART, swOpenDocOptions_Silent, "", errs, warns)
                End If
                If Not m Is Nothing Then
                    SetGlobals m, used
                    m.ForceRebuild3 False
                    m.Save3 swSaveAsOptions_Silent, errs, warns
                End If
            End If
        Next i
    End If

    ' 3) report parameters that no document uses (template drift)
    Dim nm As Variant
    For Each nm In gNames
        If Not InCollection(used, CStr(nm)) Then Log "!! No global variable """ & nm & """ in the template"
    Next nm

    asm.ForceRebuild3 False
    asm.EditRebuild3
    asm.Save3 swSaveAsOptions_Silent + swSaveAsOptions_SaveReferenced, errs, warns
    asm.ShowNamedView2 "*Isometric", -1
    asm.ViewZoomtofit2

    swApp.SendMsgToUser2 "Rocket built in:" & vbCrLf & destDir & vbCrLf & vbCrLf & gLog, swMbInformation, swMbOk
End Sub

'--- Pack and Go the master template into destDir; returns the new assembly path
Function PackAndGoTemplate(destDir As String) As String
    Dim errs As Long, warns As Long
    Dim tpl As SldWorks.ModelDoc2
    Set tpl = swApp.OpenDoc6(TEMPLATE_ASM, swDocASSEMBLY, swOpenDocOptions_Silent + swOpenDocOptions_ReadOnly, "", errs, warns)
    If tpl Is Nothing Then
        swApp.SendMsgToUser2 "Could not open template " & TEMPLATE_ASM, swMbStop, swMbOk
        Exit Function
    End If
    Dim pg As SldWorks.PackAndGo
    Set pg = tpl.Extension.GetPackAndGo
    pg.IncludeDrawings = True
    pg.IncludeSimulationResults = False
    pg.IncludeToolboxComponents = True
    pg.FlattenToSingleFolder = True
    pg.SetSaveToName True, destDir
    Dim st As Variant
    st = tpl.Extension.SavePackAndGo(pg)
    Dim tplTitle As String
    tplTitle = tpl.GetTitle
    swApp.CloseDoc tplTitle
    PackAndGoTemplate = destDir & Mid(TEMPLATE_ASM, InStrRev(TEMPLATE_ASM, "\") + 1)
    If Dir(PackAndGoTemplate) = "" Then
        swApp.SendMsgToUser2 "Pack and Go did not produce " & PackAndGoTemplate, swMbStop, swMbOk
        PackAndGoTemplate = ""
    End If
End Function

'--- Replace "name"= ... for every global variable in this doc that we have a value for
Sub SetGlobals(doc As SldWorks.ModelDoc2, used As Collection)
    Dim em As SldWorks.EquationMgr
    Set em = doc.GetEquationMgr
    If em Is Nothing Then Exit Sub
    Dim i As Long, eq As String, nm As String, n As Long
    For i = 0 To em.GetCount - 1
        If em.GlobalVariable(i) Then
            eq = em.Equation(i)
            nm = LeftName(eq)
            If InCollection(gValues, nm) Then
                em.Equation(i) = """" & nm & """= " & gValues(nm)
                If Not InCollection(used, nm) Then used.Add nm, nm
                n = n + 1
            End If
        End If
    Next i
    em.EvaluateAll
    If n > 0 Then Log doc.GetTitle & ": " & n & " variables"
End Sub

'--- Parse rocket_params.txt:   "name"= value   'comment
Function ReadParams(path As String) As Boolean
    Set gNames = New Collection
    Set gValues = New Collection
    Dim f As Integer, ln As String, nm As String, v As String, k As Long
    f = FreeFile
    Open path For Input As #f
    Do While Not EOF(f)
        Line Input #f, ln
        ln = Trim(ln)
        If Left(ln, 1) = """" Then
            nm = LeftName(ln)
            k = InStr(ln, "=")
            v = Mid(ln, k + 1)
            If InStr(v, "'") > 0 Then v = Left(v, InStr(v, "'") - 1)
            v = Trim(v)
            If nm <> "" And v <> "" And Not InCollection(gValues, nm) Then
                gNames.Add nm
                gValues.Add v, nm
            End If
        End If
    Loop
    Close #f
    If gNames.Count = 0 Then
        swApp.SendMsgToUser2 "No parameters found in " & path & vbCrLf & "Is this an ork2sw rocket_params.txt?", swMbStop, swMbOk
        Exit Function
    End If
    ReadParams = True
End Function

Function ParamValue(nm As String) As String
    If InCollection(gValues, nm) Then ParamValue = gValues(nm) Else ParamValue = ""
End Function

Function LeftName(eq As String) As String
    Dim a As Long, b As Long
    a = InStr(eq, """")
    If a = 0 Then Exit Function
    b = InStr(a + 1, eq, """")
    If b = 0 Then Exit Function
    LeftName = Mid(eq, a + 1, b - a - 1)
End Function

Function InCollection(col As Collection, key As String) As Boolean
    On Error GoTo nope
    Dim tmp As Variant
    tmp = col(key)
    InCollection = True
    Exit Function
nope:
    InCollection = False
End Function

Sub Log(s As String)
    gLog = gLog & s & vbCrLf
End Sub
