//+------------------------------------------------------------------+
//| Candle DNA - Narrow Asia London Fade v1.00                       |
//| MT5 Expert Advisor                                                |
//+------------------------------------------------------------------+
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

input group "Core Strategy"
input double InpMaxAsiaRangePips = 21.72;
input double InpMinRelVol        = 1.60;
input int    InpRelVolLookback   = 20;
input double InpStopRangeMult    = 1.00;

input group "Broker Server Time"
input int InpAsiaStartHour   = 2;
input int InpAsiaStartMinute = 0;
input int InpAsiaEndHour     = 10;
input int InpAsiaEndMinute   = 0;
input int InpTradeEndHour    = 14;
input int InpTradeEndMinute  = 0;

input group "Execution"
input double InpLots              = 0.01;
input ulong  InpMagic             = 26082801;
input int    InpDeviationPoints   = 20;
input bool   InpAllowLong         = true;
input bool   InpAllowShort        = true;

input group "Safety / Testing"
input bool InpUseDateFilter = false;
input datetime InpStartDate = D'2020.01.01 00:00';
input datetime InpEndDate   = D'2026.12.31 23:59';

// -------------------- state --------------------
datetime g_lastM5BarTime = 0;
int      g_dayKey = -1;
double   g_asiaHigh = 0.0, g_asiaLow = 0.0, g_asiaMid = 0.0, g_asiaRangePips = 0.0;
bool     g_rangeStarted = false, g_rangeFrozen = false, g_narrowAsia = false;
bool     g_firstBreakSeen = false, g_pendingPlaced = false, g_tradedToday = false;
ulong    g_pendingTicket = 0;

// -------------------- helpers --------------------
double PipSize()
{
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   return (digits==3 || digits==5) ? point*10.0 : point;
}

double NormalizePrice(double p){ return NormalizeDouble(p,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS)); }

int MinuteOfDay(datetime t)
{
   MqlDateTime d; TimeToStruct(t,d); return d.hour*60+d.min;
}

int DayKey(datetime t)
{
   MqlDateTime d; TimeToStruct(t,d); return d.year*10000+d.mon*100+d.day;
}

bool DateAllowed(datetime t)
{
   return !InpUseDateFilter || (t>=InpStartDate && t<=InpEndDate);
}

int AsiaStartMinute(){ return InpAsiaStartHour*60+InpAsiaStartMinute; }
int AsiaEndMinute(){ return InpAsiaEndHour*60+InpAsiaEndMinute; }
int TradeEndMinute(){ return InpTradeEndHour*60+InpTradeEndMinute; }

bool IsOurPositionOpen()
{
   if(!PositionSelect(_Symbol)) return false;
   return (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;
}

bool HasOurPendingOrder()
{
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0) continue;
      if(OrderGetString(ORDER_SYMBOL)!=_Symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=InpMagic) continue;
      ENUM_ORDER_TYPE type=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_SELL_STOP || type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_SELL_LIMIT)
      {
         g_pendingTicket=ticket; return true;
      }
   }
   g_pendingTicket=0; return false;
}

void CancelOurPendingOrders()
{
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0) continue;
      if(OrderGetString(ORDER_SYMBOL)!=_Symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=InpMagic) continue;
      ENUM_ORDER_TYPE type=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_SELL_STOP || type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_SELL_LIMIT)
         trade.OrderDelete(ticket);
   }
   g_pendingTicket=0; g_pendingPlaced=false;
}

void ResetDay(datetime t)
{
   CancelOurPendingOrders();
   g_dayKey=DayKey(t);
   g_asiaHigh=g_asiaLow=g_asiaMid=g_asiaRangePips=0.0;
   g_rangeStarted=g_rangeFrozen=g_narrowAsia=false;
   g_firstBreakSeen=g_pendingPlaced=g_tradedToday=false;
   g_pendingTicket=0;
}

double RelativeVolumeClosedBar(int shift)
{
   if(InpRelVolLookback<2) return 0.0;
   long cur=iVolume(_Symbol,PERIOD_M5,shift);
   if(cur<=0) return 0.0;
   double sum=0.0;
   for(int i=shift;i<shift+InpRelVolLookback;i++)
   {
      long v=iVolume(_Symbol,PERIOD_M5,i);
      if(v<=0) return 0.0;
      sum+=(double)v;
   }
   double avg=sum/InpRelVolLookback;
   return avg>0 ? (double)cur/avg : 0.0;
}

bool PendingDistanceValid(ENUM_ORDER_TYPE type,double entry)
{
   MqlTick tick; if(!SymbolInfoTick(_Symbol,tick)) return false;
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double minDist=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*point;
   if(type==ORDER_TYPE_BUY_STOP) return (entry-tick.ask)>=minDist;
   if(type==ORDER_TYPE_SELL_STOP) return (tick.bid-entry)>=minDist;
   return false;
}

void FreezeAsiaRange()
{
   if(!g_rangeStarted || g_rangeFrozen || g_asiaHigh<=g_asiaLow) return;
   double pip=PipSize();
   g_asiaMid=(g_asiaHigh+g_asiaLow)/2.0;
   g_asiaRangePips=(g_asiaHigh-g_asiaLow)/pip;
   g_rangeFrozen=true;
   g_narrowAsia=(g_asiaRangePips<=InpMaxAsiaRangePips);
   Print("Asia frozen: range=",DoubleToString(g_asiaRangePips,2),"p narrow=",g_narrowAsia);
}

void PlaceBoundaryReentry(bool highBreak,double relVol)
{
   if(g_pendingPlaced || HasOurPendingOrder() || IsOurPositionOpen()) return;

   double pip=PipSize();
   double entry=highBreak ? g_asiaHigh : g_asiaLow;
   double stopDist=g_asiaRangePips*InpStopRangeMult*pip;
   double sl=highBreak ? entry+stopDist : entry-stopDist;
   double tp=g_asiaMid;
   entry=NormalizePrice(entry); sl=NormalizePrice(sl); tp=NormalizePrice(tp);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);

   bool sent=false;
   if(highBreak && InpAllowShort && PendingDistanceValid(ORDER_TYPE_SELL_STOP,entry))
      sent=trade.SellStop(InpLots,entry,_Symbol,sl,tp,ORDER_TIME_DAY,0,"CandleDNA short reentry");
   else if(!highBreak && InpAllowLong && PendingDistanceValid(ORDER_TYPE_BUY_STOP,entry))
      sent=trade.BuyStop(InpLots,entry,_Symbol,sl,tp,ORDER_TIME_DAY,0,"CandleDNA long reentry");

   if(sent)
   {
      g_pendingPlaced=true; HasOurPendingOrder();
      Print("Qualified breakout. RelVol=",DoubleToString(relVol,2)," entry=",DoubleToString(entry,_Digits)," sl=",DoubleToString(sl,_Digits)," tp=",DoubleToString(tp,_Digits));
   }
   else
      Print("Qualified breakout but pending order not placed: ",trade.ResultRetcodeDescription());
}

void ProcessClosedM5Bar()
{
   datetime barTime=iTime(_Symbol,PERIOD_M5,1);
   if(barTime<=0 || !DateAllowed(barTime)) return;

   if(DayKey(barTime)!=g_dayKey) ResetDay(barTime);

   int minute=MinuteOfDay(barTime);
   int asiaStart=AsiaStartMinute(), asiaEnd=AsiaEndMinute(), tradeEnd=TradeEndMinute();
   double h=iHigh(_Symbol,PERIOD_M5,1), l=iLow(_Symbol,PERIOD_M5,1);

   if(minute>=asiaStart && minute<asiaEnd)
   {
      if(!g_rangeStarted){ g_rangeStarted=true; g_asiaHigh=h; g_asiaLow=l; }
      else { if(h>g_asiaHigh) g_asiaHigh=h; if(l<g_asiaLow) g_asiaLow=l; }
      return;
   }

   if(minute>=asiaEnd && !g_rangeFrozen) FreezeAsiaRange();

   if(minute>=tradeEnd)
   {
      if(!IsOurPositionOpen()) CancelOurPendingOrders();
      return;
   }

   if(!g_rangeFrozen || !g_narrowAsia || g_firstBreakSeen || g_tradedToday || minute<asiaEnd) return;

   bool breakHigh=(h>=g_asiaHigh), breakLow=(l<=g_asiaLow);
   if(!breakHigh && !breakLow) return;

   if(breakHigh && breakLow)
   {
      g_firstBreakSeen=true;
      Print("Ambiguous first-break bar. Day discarded.");
      return;
   }

   g_firstBreakSeen=true;
   double relVol=RelativeVolumeClosedBar(1);
   if(relVol<InpMinRelVol)
   {
      Print("First break failed RelVol. relVol=",DoubleToString(relVol,2));
      return;
   }

   PlaceBoundaryReentry(breakHigh,relVol);
}

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   Print("Candle DNA Narrow Asia London Fade EA initialized. Uses M5 logic.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ Comment(""); }

void OnTick()
{
   datetime cur=iTime(_Symbol,PERIOD_M5,0);
   if(cur!=g_lastM5BarTime)
   {
      g_lastM5BarTime=cur;
      ProcessClosedM5Bar();
   }

   if(IsOurPositionOpen())
   {
      g_tradedToday=true;
      g_pendingPlaced=false;
      g_pendingTicket=0;
   }

   datetime now=TimeCurrent();
   if(DayKey(now)==g_dayKey && MinuteOfDay(now)>=TradeEndMinute() && !IsOurPositionOpen())
      CancelOurPendingOrders();

   Comment("Candle DNA EA\n",
           "Asia Range: ",(g_rangeFrozen?DoubleToString(g_asiaRangePips,2)+" pips":"building"),"\n",
           "Narrow: ",(g_narrowAsia?"YES":"NO"),"\n",
           "First Break Seen: ",(g_firstBreakSeen?"YES":"NO"),"\n",
           "Pending: ",(HasOurPendingOrder()?"YES":"NO"),"\n",
           "Traded Today: ",(g_tradedToday?"YES":"NO"));
}
