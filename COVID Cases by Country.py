import datetime
import dateutil
import pandas as pd
import requests
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go


# Functions

def moving_avg(df, freq):
    ma_df = df.copy()
    ma_df = ma_df.set_index([cols.freq,cols.date])
    ma_df = ma_df.groupby([cols.region, cols.country])[[i for i in ma_df.columns.tolist() if not i in [cols.region, cols.country]]].rolling(freq).mean()
    ma_df = ma_df.reset_index()
    ma_df[cols.freq] = f'{freq}-day Moving Average'

    # remove jagged edges: drop empty up to first valid index, drop empty after last valid index
    ma_df = pd.melt(ma_df, id_vars=cols.base)
    ma_df = ma_df[(ma_df.groupby([i for i in ma_df if i not in [cols.date,'value']])['value'].bfill().notnull())&
                  (ma_df.groupby([i for i in ma_df if i not in [cols.date,'value']])['value'].ffill().notnull())]
    ma_df = pd.pivot_table(ma_df,index=cols.base,columns=['variable'],values='value')
    ma_df = ma_df.reset_index()

    ma_df = ma_df[df.columns.tolist()]
    return(ma_df)


def get_pop(cty):
    url_root = 'https://restcountries.com/v3.1/name/'
    url_suffix = '?fields=population'

    response = requests.get(url_root + ''.join(cty.lower().split()) + url_suffix)
    json_data = response.json()
    return(json_data[0]['population'])


# merge populations into cases df to find number of cases per million people
def merge_pop(df, pop_dict):
    pop_df = pd.DataFrame(pop_dict.items(), columns=[cols.country, cols.pop])
    pop_df[cols.pop] = pop_df[cols.pop] / 10**6

    merged_df = df.merge(pop_df, how='left')

    for i in cols.data:
        merged_df[f'{i} per Million Population'] = merged_df[i] / merged_df[cols.pop]

    return(merged_df)


# latest date for all countries
def last_date(df):
    latest = df.sort_values(by=cols.date).drop_duplicates(subset=cols.country, keep='last')
    latest = latest[latest[cols.cases_new]>0].reset_index(drop=True)
    return(latest)


def plot_timeseries(df, country_list, freq, no_months=12, export=False):

    meta = {'x-axis':cols.date,
            'y-axis':f'{cols.cases_new} per Million Population',
            'fontsize':8,
            cols.freq:freq,
            'date from':(datetime.datetime.now() - dateutil.relativedelta.relativedelta(months=no_months)).date()}
    meta['title'] = f'{meta["y-axis"]} ({freq})'

    plt.rcParams.update({'font.size':meta['fontsize']}) # default font size

    fig, ax = plt.subplots(figsize=(8,4))

    # df by frequency and date range. will use loop to plot each country series.
    plot_df = df.loc[(df[cols.freq]==meta[cols.freq])&
                     (df[cols.date]>=meta['date from'])]

    for cty in country_list:
        ax.plot(plot_df.loc[(plot_df[cols.country]==cty)][meta['x-axis']],
                plot_df.loc[(plot_df[cols.country]==cty)][meta['y-axis']], label=cty)

    # chart title, legend, axis names, rotate x-axis labels
    ax.set_title(meta['title'],fontweight='bold')
    ax.legend(loc='upper left')
    for tick in ax.get_xticklabels():
        tick.set_rotation(90)

    # x-axis: space out axis for subplot and set tick frequency
    ax.set_xlim(plot_df[cols.date].min(), plot_df[cols.date].max())
    ax.xaxis.set_ticks(pd.date_range(plot_df[cols.date].min(), plot_df[cols.date].max(), freq='w'))

    # y-axis: min limit is 0, number format include comma
    ax.set_ylim(bottom=0)
    ax.yaxis.set_ticks(ax.get_yticks().tolist())
    ax.set_yticklabels(['{:,}'.format(int(x)) for x in ax.get_yticks().tolist()])

    # spines and ticks
    ax.spines['top'].set_color('none')
    ax.spines['right'].set_color('none')

    plt.tight_layout()
    plt.show()

    if export:
        fig.savefig(f'{meta["title"]}.jpg', bbox_inches='tight', format='jpg', dpi=360)


def sunburst_data(df, root_name, col_plot):
    # each observation in parent must occur in labels
    data = df.copy()

    data_parent = data.groupby([cols.region,cols.date],as_index=False)[cols.data].sum()
    data_parent[cols.country] = data_parent[cols.region]
    data_parent[cols.region] = root_name

    data_root = data.copy()
    data_root[cols.country] = root_name
    data_root = data_root.groupby([cols.country,cols.date],as_index=False)[cols.data].sum()

    data = pd.concat([data, data_parent, data_root]).reset_index(drop=True)
    data = dict(labels=data[cols.country].tolist(),
                parents=data[cols.region].tolist(),
                values=data[col_plot].tolist())
    return(data)


def plot_go_sunburst1(df, root_name, col_plot):
    date = str(list(set(df[cols.date]))[0].strftime('%d %b %Y'))

    # hover: unable to format to include thousands separator (inconsistent when hovering)
    # hover: unable to format percentages to 1dp
    fig = go.Figure(go.Sunburst(**sunburst_data(latest, 'World', col_plot),
                                branchvalues='total',
                                customdata=[cols.date],
                                texttemplate='%{label}<br>%{value:,.0f}',
                                hovertext=date,
                                hoverinfo='label+value+percent parent+percent root+text'))

    fig.update_layout(title={'text':f'<b>{col_plot} on {date}<b>', 'x':0.5, 'y':0.88, 'font':{'size':14}})

    fig.show()


def plot_go_sunburst2(df, root_name, col_plot):
    date = str(list(set(df[cols.date]))[0].strftime('%d %b %Y'))

    fig = go.Figure(go.Sunburst(**sunburst_data(latest, 'World', col_plot),
                                branchvalues='total',
                                customdata=[cols.date],
                                texttemplate='%{label}<br>%{value:,.0f}'))

    fig.update_layout(title={'text':f'<b>{col_plot} on {date}<b>', 'x':0.5, 'y':0.88, 'font':{'size':14}})

    # unable to add customdata
    # unable to customise to show % root+parent at child level, and root only at parent level
    fig.update_traces(hovertemplate='%{label}<br>%{value:,.0f}<br>%{percentParent:.1%} of %{parent}<br>%{percentRoot:.1%} of %{root}<br>%{custom_data[0]}')

    fig.show()


def plot_px_sunburst(df, root_name, col_plot):
    plot_df = df.copy()
    plot_df[cols.date] = pd.to_datetime(plot_df[cols.date]).dt.strftime('%d %b %Y')
    plot_df['root'] = root_name

    fig = px.sunburst(plot_df, path=['root', cols.region, cols.country], values=col_plot,
                      custom_data=[cols.date],
                      title=f'<b>{col_plot} on {list(set(plot_df[cols.date]))[0]}<b>',
                      color=col_plot,color_continuous_scale='orrd')

    # https://plotly.com/python/reference/sunburst/#sunburst-hovertemplate
    # unable to customise to show % root+parent at child level, and root only at parent level
    fig.update_layout(title={'x':0.5,'y':0.88,'font':{'size':14}})
    fig.update_traces(texttemplate='%{label}<br>%{value:,.0f}',
                      hovertemplate='%{label}<br>%{value:,.0f}<br>%{percentParent:.1%} of %{parent}<br>%{percentRoot:.1%} of %{root}<br>%{customdata[0]}')
    fig.show()


# Static data 

regions = {'AFRO':'Africa',
           'AMRO':'Americas',
           'EMRO':'Eastern Mediterranean',
           'EURO':'Europe',
           'SEARO':'South-East Asia',
           'WPRO':'Western Pacific'}

asean = ['Indonesia','Malaysia','Philippines','Singapore','Thailand','Viet Nam']

ma_days = 7


# +
class Cols:
    def __init__(self):
        self.freq = 'Frequency'
        self.date = 'Date Reported'
        self.region = 'Region'
        self.country = 'Country'
        self.pop = 'Population (Million)'
        self.cases_new = 'New Cases'
        self.cases_all = 'Cumulative Cases'
        self.deaths_new = 'New Deaths'
        self.deaths_all = 'Cumulative Deaths'

        self.base = [self.region, self.country, self.freq, self.date]
        self.data = [self.cases_new, self.deaths_new, self.cases_all, self.deaths_all]

        self.rename = {'WHO_region':'Region','Date_reported':self.date,
                       'New_cases':self.cases_new, 'New_deaths':self.deaths_new,
                       'Cumulative_cases':self.cases_all, 'Cumulative_deaths':self.deaths_all}

cols = Cols()
# -

# COVID cases data

# WHO COVID-19 cases
covid_url = 'https://covid19.who.int/'
covid_file = covid_url + 'WHO-COVID-19-global-data.csv'
covid_df = pd.read_csv(covid_file, encoding='utf-8')

# +
# keep only selected columns and clean df
countries_df = covid_df[[cols.country] + list(cols.rename.keys())]
countries_df = countries_df.rename(columns=cols.rename)
countries_df = countries_df[[cols.region]+[i for i in list(countries_df) if i!=cols.region]]

# rename regions to proper names
countries_df[cols.region] = countries_df[cols.region].map(regions)

# date format as pd.datetime
countries_df[cols.date] = pd.to_datetime(countries_df[cols.date]).dt.date

# +
# keep only asean
asean_df = countries_df[countries_df[cols.country].isin(asean)].reset_index(drop=True)

# add moving average
asean_df[cols.freq] = 'Actual'
asean_df = asean_df[cols.base+cols.data]
asean_df = pd.concat([asean_df, moving_avg(asean_df, ma_days)]).reset_index(drop=True)
# -

# Country population data (https://restcountries.com)

pop = {}
for cty in asean:
    pop[cty] = get_pop(cty)

asean_df_pop = merge_pop(asean_df, pop)

# Plot charts 

plot_timeseries(df=asean_df_pop,
                country_list=set(asean_df_pop[cols.country]),
                freq=f'{ma_days}-day Moving Average',
                no_months=12,
                export=False)

latest = last_date(countries_df)

plot_go_sunburst1(latest, 'World', cols.cases_new)

plot_go_sunburst2(latest, 'World', cols.cases_new)

plot_px_sunburst(latest, 'World', cols.cases_new)
