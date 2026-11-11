"""Type-specific SPEC headings from the supplied example plus mandatory TEXT.

This registry describes columns, not verified executable SPEC export support.
"""
REFERENCES=('CATREF','DETAIL','MATXT','CMPREF','BLTREF','TMPREF','PDAREF','PRTREF')
SELECTORS={
 'TUBE':('PBOR0','SHOP'),
 'BEND':('PBOR0','STYP','RADI','SHOP'),
 'WELD':('PBOR0','STYP','EDGE','ALLO','SHOP'),
 'ELBO':('PBOR0','STYP','TEXT','SHOP'),
 'TEE':('PBOR0','PBOR3','STYP','HEIG','TEXT','SHOP'),
 'REDU':('PBOR1','PBOR2','STYP','TEXT','SHOP'),
 'OLET':('PBOR0','PBOR3','STYP','HEIG','ANGL','TEXT','SHOP'),
 'CAP':('PBOR0','STYP','TEXT','SHOP'),
 'FLAN':('PBOR0','STYP','TEXT','SHOP'),
 'BOLT':('PBOR1','PBOR2','STYP','SHOP'),
 'GASK':('PBOR0','STYP','TEXT','SHOP'),
 'PCOM':('PBOR0','STYP','HEIG','TEXT','SHOP'),
 'INST':('PBOR0','STYP','HEIG','ANGL','TEXT','SHOP'),
 'VALV':('PBOR1','PBOR2','STYP','HEIG','TEXT','SHOP'),
}
KEYS=dict(TYPE='type',NAME='name',PBOR0='bore0',PBOR1='bore1',PBOR2='bore2',PBOR3='bore3',
          STYP='styp',RADI='radius',EDGE='edge',ALLO='allowance',HEIG='height',ANGL='angle',
          TEXT='text',SHOP='shop',CATREF='scom_id',DETAIL='detail_id',MATXT='smte_id',
          CMPREF='prop_id',BLTREF='bolt_ref',TMPREF='tmp_ref',PDAREF='pda_ref',PRTREF='prt_ref')


def headings(kind):
    fields=list(SELECTORS[kind.upper()])
    if 'TEXT' not in fields:fields.insert(fields.index('SHOP'),'TEXT')
    return ('TYPE','NAME',*fields,*REFERENCES)


def columns(kind):return tuple(KEYS[h] for h in headings(kind))
