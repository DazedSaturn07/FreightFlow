// Presentation only: Python owns aggregation; Excel owns the visible formulas.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const data=JSON.parse(await fs.readFile(path.join(root,'data/processed/excel_inputs.json'),'utf8'));
const out=path.join(root,'outputs/freightflow'), previews=path.join(root,'artifacts/exports/workbook_previews');
const wb=Workbook.create();
const overview=wb.worksheets.add('Overview'),lanes=wb.worksheets.add('Lane review'),source=wb.worksheets.add('Source tables'),checks=wb.worksheets.add('Checks');
const navy='#183349',copper='#A76542';
function base(s,range,title,note){
 s.showGridLines=false;s.getRange(range).format.font={name:'Arial',size:10,color:navy};
 s.getRange(range).format.verticalAlignment='center';s.getRange(range).format.rowHeight=22;
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:navy};
 s.getRange('A3').values=[[note]];s.getRange('A3').format.font={name:'Arial',size:10,italic:true,color:'#667581'};
 s.getRange('A4:N4').format.borders={bottom:{style:'thin',color:copper}};
}
function head(s,r){s.getRange(r).format={fill:navy,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:32,wrapText:true};}
base(source,'A1:L390','FreightFlow source tables','FAF5.7.1. Tonnage in thousand tons; value in millions of 2017 USD; activity in million ton-miles.');
source.getRange('A5').values=[['Source: https://www.bts.gov/faf/faf5. 2024 is an estimate; 2030 and 2050 are source forecasts.']];
source.getRangeByIndexes(6,0,data.kpi.length,5).values=data.kpi;
source.tables.add('A7:E16',true,'KpiSource');head(source,'A7:E7');
source.getRangeByIndexes(19,0,data.modes.length,6).values=data.modes;
source.tables.add('A20:F86',true,'ModeSource');head(source,'A20:F20');
source.getRangeByIndexes(6,8,data.commodities.length,4).values=data.commodities;
source.tables.add('I7:L385',true,'CommoditySource');head(source,'I7:L7');
source.getRange('A:A').format.columnWidth=11;source.getRange('B:B').format.columnWidth=22;
source.getRange('C:C').format.columnWidth=30;source.getRange('D:F').format.columnWidth=20;
source.getRange('I:J').format.columnWidth=18;source.getRange('K:K').format.columnWidth=35;source.getRange('L:L').format.columnWidth=20;
source.getRange('C8:E16').format.numberFormat='#,##0.0';source.getRange('D21:F86').format.numberFormat='#,##0.0';source.getRange('L8:L385').format.numberFormat='#,##0.0';source.freezePanes.freezeRows(7);
base(overview,'A1:N42','FreightFlow','U.S. freight network review. Select a year and trade type to compare the same population.');
overview.tabColor=navy;overview.getRange('A:N').format.columnWidth=12;
overview.getRange('A6:D6').values=[['Year',2024,'Trade type','Domestic']];
overview.getRange('B6').dataValidation={rule:{type:'list',values:['2024','2030','2050']}};
overview.getRange('D6').dataValidation={rule:{type:'list',values:['Domestic','Import','Export']}};
overview.getRange('B6').format.fill='#FFF0D7';overview.getRange('D6').format.fill='#FFF0D7';overview.getRange('D:D').format.columnWidth=20;overview.getRange('F:F').format.columnWidth=20;
overview.getRange('A9:F9').values=[['Tonnage (ktons)',null,'Value (2017 USD M)',null,'Ton-miles (M)',null]];
for(const [target,col] of [['B10','C'],['D10','D'],['F10','E']])overview.getRange(target).formulas=[[`=SUMIFS('Source tables'!$${col}$8:$${col}$16,'Source tables'!$A$8:$A$16,$B$6,'Source tables'!$B$8:$B$16,$D$6)`]];
overview.getRange('B10:F10').format.font={name:'Arial',size:16,bold:true,color:copper};overview.getRange('B10:F10').format.numberFormat='#,##0';
overview.getRange('A13:C21').values=[['Mode','Tonnage (ktons)','Share'],...['Truck','Rail','Water','Air (include truck-air)','Multiple modes & mail','Pipeline','Other and unknown','No domestic mode'].map(n=>[n,null,null])];head(overview,'A13:C13');
for(let r=14;r<=21;r++){
 overview.getRange(`B${r}`).formulas=[[`=SUMIFS('Source tables'!$D$21:$D$86,'Source tables'!$A$21:$A$86,$B$6,'Source tables'!$B$21:$B$86,$D$6,'Source tables'!$C$21:$C$86,A${r})`]];
 overview.getRange(`C${r}`).formulas=[[`=IF($B$10=0,"",B${r}/$B$10)`]];
}
overview.getRange('A:A').format.columnWidth=29;overview.getRange('B:B').format.columnWidth=19;
overview.getRange('B14:B21').format.numberFormat='#,##0.0';overview.getRange('C14:C21').format.numberFormat='0.0%';
const chart=overview.charts.add('bar',[overview.getRange('A13:A21'),overview.getRange('B13:B21')]);
chart.title='Freight tonnage by mode (ktons)';chart.titleTextStyle.typeface='Arial';chart.titleTextStyle.fontSize=12;chart.hasLegend=false;
chart.xAxis={axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:10}};
chart.yAxis={numberFormatCode:'#,##0',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:10}};
chart.series.items[0].fill=copper;chart.setPosition('E13','N29');
overview.getRange('A25:C28').values=[['Year','Tonnage (ktons)','Source basis'],[2024,null,'Baseline estimate'],[2030,null,'Source forecast'],[2050,null,'Source forecast']];head(overview,'A25:C25');
for(let r=26;r<=28;r++)overview.getRange(`B${r}`).formulas=[[`=SUMIFS('Source tables'!$C$8:$C$16,'Source tables'!$A$8:$A$16,A${r},'Source tables'!$B$8:$B$16,$D$6)`]];
overview.getRange('B26:B28').format.numberFormat='#,##0.0';
overview.getRange('A31:B32').values=[['2024 to 2050 scenario growth',null],['Compound annual growth',null]];
overview.getRange('B31').formulas=[['=IF(B26=0,"",B28/B26-1)']];overview.getRange('B32').formulas=[['=IF(OR(B26<=0,B28<=0),"",(B28/B26)^(1/26)-1)']];overview.getRange('B31:B32').format.numberFormat='0.0%';
overview.getRange('A35').values=[['Forecast values describe possible future flows, not measured capacity.']];
overview.getRange('A37').values=[['Decision: investigate candidate lanes, then validate capacity, cost and service with operational data.']];
overview.getRange('A39').values=[['Lane review contains 250 ranked candidates with at least 1,000 ktons in 2024 and modes 1-6.']];
base(lanes,'A1:J260','Lane review','Top 250 candidates by growth-density index. Table filters apply to this shortlist only.');
lanes.getRange('A5').values=[['Index = growth percentile x value-density percentile across positive-baseline source lanes.']];
const rows=[['Trade','Origin','Destination','Mode','2024 ktons','2050 ktons','CAGR','2017 USD M/kton','Index','Review'],...data.lanes.slice(1).map(r=>[...r,null])];
lanes.getRangeByIndexes(6,0,rows.length,10).values=rows;lanes.tables.add('A7:J257',true,'LaneShortlist');head(lanes,'A7:J7');
for(let r=8;r<=257;r++)lanes.getRange(`J${r}`).formulas=[[`=IF(B${r}=C${r},"Within-zone flow","Between-zone flow")`]];
lanes.getRange('A:A').format.columnWidth=14;lanes.getRange('B:C').format.columnWidth=30;lanes.getRange('D:D').format.columnWidth=29;
lanes.getRange('E:F').format.columnWidth=18;lanes.getRange('G:I').format.columnWidth=19;lanes.getRange('J:J').format.columnWidth=25;
lanes.getRange('E8:F257').format.numberFormat='#,##0.0';lanes.getRange('G8:G257').format.numberFormat='0.0%';lanes.getRange('H8:I257').format.numberFormat='0.000';lanes.freezePanes.freezeRows(7);
base(checks,'A1:G37','KPI reconciliation','Independent raw-source totals versus published marts. Absolute tolerance: 0.000001.');
checks.getRangeByIndexes(6,0,28,7).values=[['Year','Trade code','Metric','Source value','Published value','Difference','Status'],...data.reconciliation.slice(1).map(r=>[...r.slice(0,5),null,null])];
head(checks,'A7:G7');checks.tables.add('A7:G34',true,'KpiChecks');
checks.getRange('F8').formulas=[['=D8-E8']];checks.getRange('F8:F34').fillDown();checks.getRange('G8').formulas=[['=IF(ABS(F8)<0.000001,"PASS","FAIL")']];checks.getRange('G8:G34').fillDown();
checks.getRange('A:B').format.columnWidth=13;checks.getRange('C:C').format.columnWidth=22;checks.getRange('D:F').format.columnWidth=24;checks.getRange('G:G').format.columnWidth=14;
checks.getRange('D8:F34').format.numberFormat='#,##0.000000';checks.getRange('G8:G34').conditionalFormats.add('containsText',{text:'FAIL',format:{fill:'#FEE2E2',font:{bold:true,color:'#B91C1C'}}});checks.freezePanes.freezeRows(7);
for (const s of [lanes,source,checks]) { for (const t of s.tables.items) { t.style='TableStyleLight1'; t.showFilterButton=true; } }
wb.recalculate();
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'Formula error scan'});
await fs.mkdir(out,{recursive:true});await fs.mkdir(previews,{recursive:true});await fs.writeFile(path.join(previews,'formula_scan.json'),scan.ndjson);
for(const [s,range] of [[overview,'A1:N41'],[lanes,'A1:J18'],[source,'A1:L17'],[checks,'A1:G36']]){
 const png=await wb.render({sheetName:s.name,range,scale:1.5,format:'png'});await fs.writeFile(path.join(previews,`${s.name.replaceAll(' ','_')}.png`),new Uint8Array(await png.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'FreightFlow_Operations.xlsx'));
console.log(scan.ndjson);console.log(path.join(out,'FreightFlow_Operations.xlsx'));
