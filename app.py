import plotly.express as px
import pandas as pd
import numpy as np
import re
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_plotly
from os import listdir
from os.path import isfile, join, exists
datapath = "voting_data\\data"
if exists(datapath) == False:
    datapath = "data" #for shinyapps.io
onlyfiles = [f for f in listdir(datapath) if isfile(join(datapath, f))]
extracted = [re.split("__", filename) for filename in onlyfiles]
states = [sublist[1] for sublist in extracted]
ustates = list(set(states))
print(ustates) #DEBUG_PRINT
columns = ['date','state','elect','suffix']
dd = pd.DataFrame(extracted, columns=columns)
dd['state'] = dd['state'].str.upper()
dd['year'] = dd['date'].astype(int)//10000
dd['election'] = dd['date'].str[4:]+"_"+dd['elect']
rlist = {}
state0 = dd['state'][0]
edate0 = ""
race_choices = None
with open("voting_data.htm", 'r') as file: 
    html_as_string = file.read()

app_ui = ui.page_sidebar(
     ui.sidebar(
        ui.input_select(
            "state",
            "STATE",
            choices=[]
         ),
        ui.input_select(
            "year",
            "YEAR",
            choices=[]
        ),
        ui.input_select(
            "election",
            "ELECTION",
            choices=[]
        ),
        ui.input_select(
            "county",
            "COUNTY",
            choices=[]
        ),
        ui.input_select(
            "votetype",
            "VOTETYPE",
            choices=[]
        ),
        ui.input_select(
            "office",
            "OFFICE",
            choices=[]
        ),
        ui.row(
            ui.column(6,
                ui.input_action_button("add_race", "Add", style="background-color:#00ff00")
            ),
            ui.column(6,
                ui.input_action_button("clear_races", "Clear", style="background-color:#ff0000")
            )
        ),
         ui.input_select(
            "races",
            "RACES",
            choices=[],
            multiple=True
        ),
        ui.input_select(
            "pgroup",
            "PRECINCT GROUP",
            choices=[]
        ),
        ui.input_checkbox("demrep","DEM/REP only", True),
        ui.input_checkbox("demrep_comb","DEM/REP combine", True),
        ui.input_checkbox("calctotal","Calculate Total", True),
        ui.input_checkbox("varysize","Dot Size by Total", True),
        ui.input_checkbox("plotvotes","Plot votes (else voteshares)", True),
        ui.input_numeric("maxsize","Max Dot Size",value=15,min=1),
        ui.input_numeric("decimals","Decimal Places",value=1,min=0),
        width=350
    ),
    ui.navset_tab(
        ui.nav_panel(
            "Plot",
            output_widget("plotly")
        ),
        ui.nav_panel(
            "Dropoff",
            output_widget("dropoff")
        ),
        ui.nav_panel(
            "Text",
            ui.output_data_frame("summary_data")
        ),
        ui.nav_panel(
            "Usage",
            ui.HTML(html_as_string)
        )
    ),
     title = "U.S. Election Data"
)

def server(input, output, session):
    def filter_data(dd):
        print("START server") #DEBUG_PRINT
        dd = dd.replace({np.nan: 0})
        dd = dd[dd['party'] != 0]
        if (input.county() != "(all)"):
            dd = dd[dd['county'] == input.county()]
        if (input.votetype() == "Total"):
            if (input.calctotal()):
                tt = dd[dd['votetype'] != "Total"]
                if len(tt) > 0:
                    dd = tt
                    dd = dd.assign(votetype="Total")
                    dd = dd.groupby(['county','precinct','office','district','party','candidate','votetype'], as_index=False)[['votes']].agg('sum')
        else:
            dd = dd[dd['votetype'] == input.votetype()]
        gg = dd.groupby(['county','precinct','office','district','votetype'], as_index=False)[['votes']].agg('sum')
        gg = gg.rename(columns={'votes': 'total'})
        ee = pd.merge(dd, gg, how="outer", on=["county", "precinct", "office", "district", "votetype"])
        if (input.demrep_comb()):
            demcand  = set(ee[ee.party == "DEM"]['candidate'])
            if len(demcand) > 0:
                sdemcand = list(demcand)[0] #loop if more than one?
                sdemcand = sdemcand.replace("DEM ","")
                ee['candidate'] = ee['candidate'].apply(lambda x:sdemcand if pd.notnull(x) and pd.Series(x).str.contains(sdemcand, regex=True)[0] else x)
                ee.loc[ee['candidate'] == sdemcand, 'party'] = "DEM"
                repcand  = set(ee[ee.party == "REP"]['candidate'])
                srepcand = list(repcand)[0] #loop if more than one?
                srepcand = srepcand.replace("REP ","")
                ee['candidate'] = ee['candidate'].apply(lambda x:srepcand if pd.notnull(x) and pd.Series(x).str.contains(srepcand, regex=True)[0] else x)
                ee.loc[ee['candidate'] == srepcand, 'party'] = "REP"
                ee = ee.groupby(['county','precinct','office','district','party','candidate','votetype','total'], as_index=False)[['votes']].agg('sum')
                               
        ee = ee.assign(voteshare = 100 * ee['votes'] / ee['total'])
        if (input.demrep()):
            ee = ee[ee['party'].isin (["DEM","REP"])]
        tt = ee[ee['precinct'] == "ALL`"]
        if (len(tt) > 0):
            ee = ee[ee['precinct'] != "ALL"]
        return(ee)

    def do_add_race():
        print("START do_add_race()") #DEBUG_PRINT
        dd = read_csv()
        if (type(dd) == pd.core.frame.DataFrame and type(input.office()) != type(None)):
            if (input.add_race() > 0):
                dd = dd[dd['office'] == input.office()]
                race_name = input.state()+"_"+input.year()[2:4]+input.election()[0:4]+"_"+input.office()
                rlist[race_name] = dd
                print("-----> ROWS SAVED in rlist["+race_name+"] = "+str(len(dd))) #DEBUG_PRINT
                choices = list(rlist.keys())
                ui.update_select(
                    "races",
                    choices=choices,
                    selected=race_name
                )
                if len(rlist) == 1:
                    set_pgroups(dd.precinct)

    def get_precint_indices(ff):
        pp = list(set(ff.precinct))
        ll = []
        nn = []
        oo = []
        for i in range(0,len(list(pp)),1):
            match = re.match(r"([a-zA-Z ]+)(\d+)([a-zA-Z0-9\(\) ]*)", str(list(pp)[i]))
            if match:
                letters = match.group(1)
                numbers = int(match.group(2))
                ll.append(letters.strip())
                nn.append(numbers)
                oo.append(match.group(3))
            else:
                ll.append(list(pp)[i])
                nn.append(0)
                oo.append("")
        dd = pd.DataFrame({
            'precinct': pp,
            'str': ll,
            'int': nn,
            'oth': oo
        })
        dd = dd.sort_values(by=['str','int','oth'], ascending=True)
        dd.insert(0,'ind', range(1, (len(dd)+1)))
        xx = dict(zip(dd.precinct, dd.ind))
        return xx
        
    def get_race():
        global state0
        global edate0
        ee = None
        if (len(rlist) > 0):
            rname = input.races()[0]
            state0 = rname[0:2]
            edate0 = edate0 = rname[5:7]+"/"+rname[7:9]+"/20"+rname[3:5]
            ee = rlist[rname]
            print("<----- ROWS READ from rlist[",rname,"]="+str(len(ee))) #DEBUG_PRINT
        else:
            dd = read_csv()
            if (type(dd) == pd.core.frame.DataFrame and type(input.office()) != type(None)):
                dd = dd[dd['office'] == input.office()]
                print("<----- ROWS READ from CSV file="+str(len(dd))) #DEBUG_PRINT
                ee = dd
        return(ee)

    def get_racei(ii):
        global state0
        global edate0
        ee = None
        if (len(rlist) > ii):
            rname = list(rlist.keys())[ii]
            if (ii == 0):
                state0 = rname[0:2]
                edate0 = rname[5:7]+"/"+rname[7:9]+"/20"+rname[3:5]
            ee = rlist[rname]
            print("<----- ROWS READ from rlist[",rname,"]="+str(len(ee))) #DEBUG_PRINT
        else:
            if (ii == 0):
                dd = read_csv()
                if (type(dd) == pd.core.frame.DataFrame and type(input.office()) != type(None)):
                    dd = dd[dd['office'] == input.office()]
                    print("<----- ROWS READ from CSV file="+str(len(dd))) #DEBUG_PRINT
                    ee = dd
                else:
                    narg = ii+1
                    print("WARNING: need to Add "+str(narg)+"th Race") #DEBUG_PRINT
        return(ee)

    def set_pgroups(pp):
        lgroups = ["(all)"]
        if (pp.dtype != "int64"):
            for i in range(0,len(list(pp))-1,1):
                match = re.match(r"([a-zA-Z ]+)(\d+)([a-zA-Z0-9\(\) ]*)", str(list(pp)[i]))
                if match:
                    letters = match.group(1)
                    lgroups.append(letters.strip())
        choices = list(set(lgroups))
        choices.sort()
        ui.update_select(
            "pgroup",
            choices=list(choices),
            selected=list(choices)[0]
        )
        return choices

    @render_plotly
    def plotly():
        print("START plotly()") #DEBUG_PRINT
        dd = get_race()
        if (type(dd) != type(None)):
            ee = filter_data(dd)
            pgroup = input.pgroup()
            if (type(pgroup) != type(None) and pgroup != "(all)"):
                ee = ee[ee['precinct'].str.startswith(pgroup)]
            ee = ee[ee['votetype'] == input.votetype()]
            if input.varysize():
                ee['size'] = ee['total']
            else:
                ee['size'] = 1
            title = ""
            if (type(input.county()) == str):
                if (len(ee) > 0):
                    title = input.county()+" County, "+state0+": "+list(ee.office)[0]+" Vote Share by Precinct Vote Total, "+edate0
                else:
                    title = input.county()+" County, "+state0+": Candidate Vote Share by Precinct Vote Total, "+edate0
            fig = px.scatter(ee, x='total', y='voteshare',
                            size='size',
                            size_max=input.maxsize(),
                            color='party', opacity=0.5,
                            title=title, height = 600,
                            hover_data=["precinct","county","candidate","party","votes"],
                            labels={
                                "voteshare":"Party Vote Share (%)",
                                "total":"Number of "+input.votetype()+" Votes by Precinct<br><i>Sources: see https://econdataus.com/voting_data.htm</i>"
                            })
            return(fig)
    
    @render_plotly
    def dropoff():
        print("START dropoff()") #DEBUG_PRINT
        input.add_race()
        dd = get_racei(0)
        ee = get_racei(1)
        if (type(dd) != type(None) and type(ee) != type(None)):
            dd = filter_data(dd)
            ee = filter_data(ee)
            dd = dd.rename(columns={'office':'office1','votes':'votes1','total':'total1','candidate':'candidate1','voteshare':'voteshare1'})
            ee = ee.rename(columns={'office':'office2','votes':'votes2','total':'total2','candidate':'candidate2','voteshare':'voteshare2'})
            ff = pd.merge(dd, ee, how="outer", on=["county", "precinct", "district","party","votetype"])
            if input.plotvotes():
                ff['dropoff'] = ff['votes1'] - ff['votes2']
                yunits = "Votes"
            else:
                ff['dropoff'] = ff['voteshare1'] - ff['voteshare2']
                yunits = "Voteshares"
            pgroup = input.pgroup()
            if (type(pgroup) != type(None) and pgroup != "(all)"):
                ff = ff[ff['precinct'].str.startswith(pgroup)]
            ff = ff[ff['votetype'] == input.votetype()]
            xx = get_precint_indices(ff)
            ff['index'] = ff['precinct'].map(xx)
            ff['size'] = ff['total1']
            if input.varysize():
                ff['size'] = ff['total1']
            else:
                ff['size'] = 1
            title = ""
            if (type(input.county()) == str):
                if (pgroup == "(all)"):
                    spgroup = ""
                else:
                    spgroup = " ("+pgroup+")"
                ii = min(ff.index)
                if (len(ff) > 0):
                    title = input.county()+" County, "+state0+spgroup+": Dropoff from "+str(ff.office1[ii])+" to "+str(ff.office2[ii])+", "+edate0
                else:
                    title = input.county()+" County, "+state0+spgroup+": Dropoff, "+edate0
            fig = px.scatter(ff, x='index', y='dropoff',
                            size='size',
                            size_max=input.maxsize(),
                            color='party', opacity=0.5,
                            title=title, height = 600,
                            hover_data=["precinct","county","candidate1","candidate2","party"],
                            labels={
                                "dropoff":"Dropoff in "+input.votetype()+" "+yunits,
                                "index":"Precinct<br><i>Sources: see https://econdataus.com/voting_data.htm</i>"
                            }
            )
            demavg = ff[ff.party == "DEM"].dropoff.mean()
            print(demavg) #DEBUG_DO - output this?
            repavg = ff[ff.party == "REP"].dropoff.mean()
            print(repavg) #DEBUG_DO - output this?
            fig.add_hline(y=demavg, line_color="blue")
            fig.add_hline(y=repavg, line_color="red")
            return(fig)
        else:
            print("WARNING: Must add at least two races to RACES textbox")
            return(None)
        
    @render.data_frame
    def summary_data():
        dd = get_race()
        ee = filter_data(dd)
        pgroup = input.pgroup()
        if (type(pgroup) != type(None) and pgroup != "(all)"):
            ee = ee[ee['precinct'].str.startswith(pgroup)]
        ee = ee[ee['votetype'] == input.votetype()]
        ee['voteshare'] = ee['voteshare'].round(input.decimals())
        tt = ee.groupby(['county','office','district','party','candidate','votetype'], as_index=False)[['votes']].agg('sum')
        tt['precinct'] = "(all)"
        tt['total'] = sum(tt['votes'])
        tt = tt.assign(voteshare = 100 * tt['votes'] / tt['total'])
        tt['voteshare'] = tt['voteshare'].round(input.decimals())
        ee = pd.concat([ee, tt], ignore_index=True)
        return render.DataGrid(ee, selection_mode="rows")
    
    @reactive.effect
    def _():
        print("START update STATE") #DEBUG_PRINT
        choices = sorted(list(set(dd.state)))
        ui.update_select(
            "state",
            choices=choices,
            selected=choices[0]
        )

    @reactive.effect
    def _():
        global state0
        print("START update YEAR") #DEBUG_PRINT
        state0 = input.state()
        if (input.state() != None):
            ee = dd[dd['state'] == input.state()]
            choices = sorted(list(set(ee.year)))
            ui.update_select(
                "year",
                choices=choices,
                selected=choices[len(choices)-1]
            )

    @reactive.effect
    def _():
        print("START update ELECTION") #DEBUG_PRINT
        if (input.state() != None and input.year() != None):
            ee = dd[dd['state'] == input.state()]
            ff = ee[ee['year'] == int(input.year())]
            choices = sorted(list(set(ff.election)))
            if (len(ff) > 0):
                ui.update_select(
                    "election",
                    choices=choices,
                    selected=choices[len(choices)-1]
                )

    @reactive.effect
    def _():
        print("START Add to Races") #DEBUG_PRINT
        input.add_race()
        with reactive.isolate():
            do_add_race()

    @reactive.effect
    def _():
        global rlist
        print("START Clear Races") #DEBUG_PRINT
        input.clear_races()
        rlist = {}
        ui.update_select(
            "races",
            choices=[]
        )

    @reactive.effect
    def _():
        print("START NEW FILE") #DEBUG_PRINT
        input.state()
        input.year()
        input.election()
        dd = read_csv()
    
    @reactive.calc
    def read_csv():
        global state0
        global edate0
        print("START READ_CSV")
        zz = None
        if (input.state() != None and input.year() != None and input.election() != None):
            date_elect = re.split("_",input.election(),maxsplit=1)
            state0 = input.state()
            edate0 = date_elect[0][0:2]+"/"+date_elect[0][2:4]+"/"+input.year()
            filepath = datapath + "/" + input.year() + date_elect[0] + "__" + str.lower(input.state()) + "__" + date_elect[1] + "__precinct.csv"
            if (exists(filepath)):
                zz = pd.read_csv(filepath)
                print(filepath+" FOUND") #DEBUG_PRINT
                if ('votetype' not in zz):
                    zz['votetype'] = "Total"
                print("##### FILE EXISTS #####") #DEBUG_PRINT
                sortedlist = sorted(list(set(zz.county)))
                if len(sortedlist) > 1:
                    choices = ['(all)'] + sortedlist
                else:
                    choices = sortedlist
                ui.update_select(
                    "county",
                    choices=choices,
                    selected=choices[0]
                )
                choices = sorted(list(set(zz.office)))
                choice0 = choices[0]
                if (choices.__contains__("President of the US")):
                    zz['office'].replace("President of the US", "US President", inplace=True)
                    choices = sorted(list(set(zz.office)))
                    choice0="US President"
                if (choices.__contains__("President")):
                    choice0="President"
                if (choices.__contains__("U.S. President")):
                    choice0="U.S. President"
                ui.update_select(
                    "office",
                    choices=choices,
                    selected=choice0
                )
                choices = sorted(list(set(zz.votetype)))
                ui.update_select(
                    "votetype",
                    choices=choices,
                    selected=choices[len(choices)-1]
                )
            else:
                print("ERROR: "+filepath+" NOT FOUND") #DEBUG_PRINT
        return(zz)

app = App(app_ui, server)
