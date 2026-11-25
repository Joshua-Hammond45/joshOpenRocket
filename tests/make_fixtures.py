"""Build synthetic .ork fixtures in OpenRocket 23.09 (file format 1.9) layout."""
import os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
IN = 0.0254

def ring(name, method, off):
    return f"""<centeringring><name>{name}</name><material type="bulk" density="630.0">Plywood (birch)</material>
<axialoffset method="{method}">{off}</axialoffset><position type="{method}">{off}</position>
<length>{0.25*IN}</length><radialposition>0.0</radialposition><radialdirection>0.0</radialdirection>
<outerradius>auto</outerradius><innerradius>auto</innerradius></centeringring>"""

def fin_can(length_in, chute_event="apogee", break_=False):
    chute = f"""<parachute><name>Parachute</name><axialoffset method="top">0.0</axialoffset>
<packedlength>0.1</packedlength><packedradius>0.03</packedradius><cd>auto 0.8</cd><material type="surface" density="0.067">Ripstop nylon</material>
<deployevent>{chute_event}</deployevent><deployaltitude>200.0</deployaltitude><deploydelay>0.0</deploydelay>
<diameter>{36*IN}</diameter><linecount>6</linecount><linelength>0.9144</linelength></parachute>
<shockcord><name>Shock cord</name><axialoffset method="top">0.1</axialoffset><packedlength>0.05</packedlength><packedradius>0.02</packedradius>
<cordlength>{(3*(length_in+ (30 if break_ else 0)+14)+6)*IN}</cordlength><material type="line" density="0.003">Tubular nylon (11 mm, 7/16 in)</material></shockcord>"""
    return f"""<bodytube><name>Body tube</name><finish>normal</finish><material type="bulk" density="1086.0">Cardboard</material>
<length>{length_in*IN}</length><thickness>{0.05*IN}</thickness><radius>auto {1.55*IN}</radius>
<subcomponents>
<innertube><name>Motor tube</name><material type="bulk" density="1086.0">Cardboard</material>
<axialoffset method="bottom">0.0</axialoffset><position type="bottom">0.0</position>
<outerradius>{0.81*IN}</outerradius><thickness>{0.06*IN}</thickness><length>{12*IN}</length>
<radialposition>0.0</radialposition><radialdirection>0.0</radialdirection><clusterconfiguration>single</clusterconfiguration>
<motormount><ignitionevent>automatic</ignitionevent><ignitiondelay>0.0</ignitiondelay><overhang>0.0</overhang>
<motor configid="a1"><type>reload</type><manufacturer>Cesaroni Technology</manufacturer><digest>x</digest>
<designation>H143SS</designation><diameter>0.038</diameter><length>0.186</length><delay>none</delay></motor>
</motormount></innertube>
{ring("Top ring", "bottom", -(12-0.25)*IN)}
{ring("Middle ring", "bottom", -(0.25+5.5)*IN)}
{ring("Bottom ring", "bottom", 0.0)}
<trapezoidfinset><name>Fins</name><material type="bulk" density="630.0">Plywood (birch)</material>
<axialoffset method="bottom">0.0</axialoffset><position type="bottom">0.0</position>
<fincount>4</fincount><radiusoffset method="surface">0.0</radiusoffset><angleoffset method="relative">0.0</angleoffset>
<rotation>0.0</rotation><thickness>{0.25*IN}</thickness><crosssection>square</crosssection><cant>0.0</cant>
<tabheight>{(1.45-0.81)*IN}</tabheight><tablength>{5.5*IN}</tablength><tabposition relativeto="front">{0.25*IN}</tabposition>
<filletradius>0.0</filletradius><rootchord>{6*IN}</rootchord><tipchord>{3*IN}</tipchord><sweeplength>{3*IN}</sweeplength><height>{3.5*IN}</height>
</trapezoidfinset>
{"" if break_ else chute}
</subcomponents></bodytube>""", chute

def sims(stab, ghv):
    return f"""<simulations><simulation status="uptodate"><name>Simulation 1</name><simulator>RK4Simulator</simulator>
<flightdata maxaltitude="900.0" maxvelocity="150.0" maxacceleration="120.0" maxmach="0.45" timetoapogee="10.0" flighttime="60.0"
groundhitvelocity="{ghv}" launchrodvelocity="18.0" deploymentvelocity="20.0">
<databranch name="Sim" types="Time,Altitude,Vertical velocity,Stability margin calibers">
<event time="0.31" type="launchrod"/>
<datapoint>0.0,0.0,0.0,NaN</datapoint><datapoint>0.1,0.5,5.0,{stab-0.1}</datapoint>
<datapoint>0.3,2.0,17.0,{stab}</datapoint><datapoint>1.0,30.0,90.0,{stab+0.3}</datapoint>
</databranch></flightdata></simulation></simulations>"""

def ork(break_=False, chute_event="apogee", stab=1.6, ghv=6.1):
    nose = f"""<nosecone><name>Nose cone</name><finish>normal</finish><material type="bulk" density="1050.0">ABS</material>
<length>{14*IN}</length><thickness>{0.1*IN}</thickness><shape>ogive</shape><shapeclipped>false</shapeclipped><shapeparameter>1.0</shapeparameter>
<aftradius>auto {1.55*IN}</aftradius><aftshoulderradius>{1.5*IN}</aftshoulderradius><aftshoulderlength>{3*IN}</aftshoulderlength>
<aftshoulderthickness>{0.1*IN}</aftshoulderthickness><aftshouldercapped>false</aftshouldercapped></nosecone>"""
    can, chute = fin_can(24 if break_ else 36, chute_event, break_)
    upper = ""
    if break_:
        upper = f"""<bodytube><name>Upper tube</name><finish>normal</finish><material type="bulk" density="1086.0">Cardboard</material>
<length>{30*IN}</length><thickness>{0.05*IN}</thickness><radius>auto</radius><subcomponents>
<tubecoupler><name>Coupler</name><material type="bulk" density="1086.0">Cardboard</material>
<axialoffset method="bottom">{3*IN}</axialoffset><outerradius>auto</outerradius><thickness>{0.06*IN}</thickness><length>{6*IN}</length>
<subcomponents><bulkhead><name>Bulkhead</name><material type="bulk" density="630.0">Plywood (birch)</material>
<axialoffset method="middle">0.0</axialoffset><length>{0.25*IN}</length><outerradius>auto</outerradius></bulkhead></subcomponents>
</tubecoupler>{chute}</subcomponents></bodytube>"""
    xml = f"""<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9" creator="OpenRocket 23.09">
<rocket><name>Test L1</name><id>x</id><axialoffset method="absolute">0.0</axialoffset>
<motorconfiguration configid="a1" default="true"/><referencetype>maximum</referencetype>
<subcomponents><stage><name>Sustainer</name><id>s</id><subcomponents>
{nose}{upper}{can}
</subcomponents></stage></subcomponents></rocket>
{sims(stab, ghv)}
</openrocket>"""
    return xml

def write(name, xml):
    p = os.path.join(HERE, "data", name)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("rocket.ork", xml)
    return p

if __name__ == "__main__":
    write("l1_single.ork", ork())
    write("l1_break.ork", ork(break_=True))
    write("l1_bad.ork", ork(chute_event="ejection", stab=0.7, ghv=11.0))
    print("fixtures written")
