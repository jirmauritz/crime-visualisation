import os
import pandas as pd
import numpy as np
from collections import OrderedDict
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.basemap import Basemap
from bokeh.io import output_file, save
from bokeh.layouts import layout, widgetbox
from bokeh.models.widgets import RadioButtonGroup
from bokeh.models import (
  GMapPlot, GMapOptions, ColumnDataSource, Circle, DataRange1d, PanTool, WheelZoomTool, BoxSelectTool,
  HoverTool, CustomJS
)

DATA_FILE = 'data/crime_homicide_subset.csv'
OUT_DIR   = 'output/'
# to display bokeh graph, insert Google API key here
API_KEY   = ''

'''
Loads data from CSV.
'''
def loadData():
    df = pd.read_csv(DATA_FILE)
    # remove two outliers (dont even lay in DC)
    df.drop(df.index[[222,758]], inplace=True)
    return df

'''
Creates background layer of a road map according to the coordinates.

params:
    lons: array of longitude
    lats: array of latitudes

returns:
    instance of Basemap with one layer of map
'''
def backgroundLayer(lons, lats):
    # compute max lon/lat
    maxLon = np.max(lons)
    maxLat = np.max(lats)
    minLon = np.min(lons)
    minLat = np.min(lats)

    # set background map to Washington DC coordinates
    m = Basemap(
        llcrnrlon=minLon, llcrnrlat=minLat,
        urcrnrlon=maxLon, urcrnrlat=maxLat,
        epsg=3395,
        resolution='i',
        projection='tmerc')

    # download map image from ArcGis web
    m.arcgisimage(service='World_Street_Map',
                  xpixels=1500,
                  dpi=512)
    return m


'''
Produces a scatterplot of crimes in DC.
The points are then colored with respect to the values of the feature.

params:
    df: pandas dataframe of crimes
    feature: one of 'OFFENSE' or 'METHOD'
'''
def scatterPlot(df, feature=None):
    lons = np.array(df['long'])
    lats = np.array(df['lat'])

    featToCol = {
        'SEX ABUSE': 'r',
        'HOMICIDE': 'b',
        'GUN': 'r',
        'KNIFE': 'b',
        'OTHERS': 'g'
    }

    colors = map(lambda feat: featToCol[feat], df[feature]) if feature is not None else ['r'] * len(df)

    plt.figure()
    m = backgroundLayer(lons, lats)
    lons, lats = m.shiftdata(lons, lats)
    for lon,lat,c in zip(lons, lats, colors):
        m.scatter(lon, lat, marker='o', color=c, alpha=0.4, latlon=True)

    # graph style
    title = 'Scatter plot of crimes in DC'
    if feature == 'OFFENSE':
        title += ' according to the type of offence'
        sex = mpatches.Circle((0.25, 0.25), color='red', label='sex abuse')
        hom = mpatches.Circle((0.25, 0.25), color='blue', label='homicide')
        plt.legend(handles=[sex, hom], prop={'size':10})
    if feature == 'METHOD':
        title += ' according to the weapon'
        gun = mpatches.Circle((0.25, 0.25), color='red', label='gun')
        knife = mpatches.Circle((0.25, 0.25), color='blue', label='knife')
        other = mpatches.Circle((0.25, 0.25), color='green', label='other')
        plt.legend(handles=[gun, knife, other], prop={'size':10})
    plt.title(title)

    # output
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)
    plt.savefig(OUT_DIR + 'scatter' + ('_' + feature.lower() if feature is not None else '') + '.png', dpi=512)


'''
Produces a heatmap of crimes in DC.

params:
    df: pandas dataframe of crimes
'''
def heatmap(df):
    lons = np.array(df['long'])
    lats = np.array(df['lat'])

    plt.figure()
    map = backgroundLayer(lons, lats)

    db = 1 # bin padding
    lon_bins = np.linspace(min(lons)-db, max(lons)+db, 500)
    lat_bins = np.linspace(min(lats)-db, max(lats)+db, 500)

    density, _, _ = np.histogram2d(lats, lons, [lat_bins, lon_bins])
    lon_bins_2d, lat_bins_2d = np.meshgrid(lon_bins, lat_bins)
    xs, ys = map(lon_bins_2d, lat_bins_2d)
    map.pcolormesh(xs, ys, density, cmap=plt.cm.jet, alpha=0.2)

    # graph style
    plt.title('Heatmap of crimes in DC')

    # output
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)
    plt.savefig(OUT_DIR + 'heatmap.png', dpi=512)


'''
Produces interactive bokeh graph in HTML.
Background layer is based on Google Maps (API key required).

params:
    df: pandas dataframe of crimes
'''
def bokeh_scatter(df):
    output_file(OUT_DIR + 'bokeh_scatter.html', title="Crimes in Washington DC")
    map_options = GMapOptions(lat=38.89511, lng=-77.03637, map_type="roadmap", zoom=11)
    plot = GMapPlot(
        x_range=DataRange1d(), y_range=DataRange1d(), map_options=map_options, api_key=API_KEY,
    )
    plot.title.text = 'Scatter plot of crimes in DC'

    source = ColumnDataSource(
        data=dict(
            color=['rgb(255, 0, 0)'] * len(df),
            lat=df['lat'],
            lon=df['long'],
            offense=df['OFFENSE'],
            weapon=df['METHOD'],
            start_date=list(df['START_DATE'])

        )
    )

    circle = Circle(x="lon", y="lat", size=5, fill_color="color", fill_alpha=0.5, line_color=None)
    plot.add_glyph(source, circle)
    plot.add_tools(PanTool(), WheelZoomTool(), BoxSelectTool(), HoverTool())
    hover = plot.select(dict(type=HoverTool))
    hover.tooltips = OrderedDict([
        ('Weapon', '@weapon'),
        ('Offense', '@offense'),
        ('Date', '@start_date'),
    ])

    callback = CustomJS(args=dict(source=source), code="""
        var data = source.data;
        var option = cb_obj.active
        switch(option) {
            case 0:
                for (i = 0; i < data['color'].length; i++) {
                    data['color'][i] = 'rgb(255,0,0)'
                }
                break;
            case 1:
                for (i = 0; i < data['color'].length; i++) {
                    if (data['offense'][i] === 'SEX ABUSE') {
                        data['color'][i] = 'rgb(255,0,0)'
                    } else {
                        data['color'][i] = 'rgb(0,0,255)'
                    }
                }
                break;
            case 2:
                for (i = 0; i < data['color'].length; i++) {
                    if (data['weapon'][i] === 'GUN') {
                        data['color'][i] = 'rgb(255,0,0)'
                    } else if (data['weapon'][i] === 'KNIFE') {
                        data['color'][i] = 'rgb(0,0,255)'
                    } else {
                        data['color'][i] = 'rgb(0,255,0)'
                    }
                }
                break;
        }
        source.trigger('change');
    """)

    button_group = RadioButtonGroup(labels=["All", "Offense (sex abuse [red], homicide [blue])",
                                            "Weapon (gun [red], knife [blue], other [green])"], active=0, callback=callback)

    l = layout([[plot, widgetbox(button_group)]])
    save(l)


# MAIN
df = loadData()

scatterPlot(df)
scatterPlot(df, 'OFFENSE')
scatterPlot(df, 'METHOD')
heatmap(df)
bokeh_scatter(df)
