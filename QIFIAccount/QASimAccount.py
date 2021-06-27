# -*- coding:utf-8 -*-
"""
Created on 2021/6/5 10:45
@author: Leo
@file:QASimAccount.py
@desc:
"""
import datetime
from qaenv import mongo_ip
from QIFIAccount import QIFI_Account
import QUANTAXIS as QA


class QIFI_SIM_Account(QIFI_Account):
    hisflag=False

    def __init__(self, username, password, model="SIM", broker_name="QAPaperTrading", trade_host=mongo_ip,init_cash=1000000):
        super().__init__(username, password, model, broker_name, trade_host, init_cash)
        self.orders_history={}
        self.trades_history={}
        self.balance_history={}
    @property
    def dtstr(self):
        if self.model=="BACKTEST" or self.hisflag==False:
            return self.datetime.replace('.', '_')
        else:
            return str(datetime.datetime.now()).replace('.', '_')

    @property
    def trading_day(self):
        if self.model == "BACKTEST" or self.hisflag==False:
            return str(self.datetime)[0:10]
        else:
            return self._trading_day

    def order_check(self, code: str, amount: int, price: float, towards: int, order_id: str) -> bool:
        '''
        :param code:
        :param amount:
        :param price:
        :param towards:
        :param order_id:
        :return:
        '''
        #增加补充检查如果是A股或港股，则代码必须存在
        try:
            int(str(code)[1])
            # code = code[0]
            try:
                if len(str(code)) == 5:
                    self.log('港股，不做代码是否存在必要性校验') #todo:待完善
                else:
                    QA.QA_fetch_security_name(str(code))
            except Exception as e:
                self.log(e)
                self.log('找不到A股代码'+code)
        except:
            self.log('非A股或港股，不做代码是否存在必要性校验或')
        return super().order_check(code,amount,price,towards,order_id)
    def add_position(self, position):
        code = self.format_code(position.code)

        if code not in self.positions.keys():
            self.positions[code] = position
            self.ask_deposit(position.open_price_long*position.volume_long_his) #todo:仅考虑多仓为，期货等待完善
            return 0
        else:
            return 1
    def settle(self):
        self.log('settle')
        self.sync()

        # self.pre_balance += (self.deposit - self.withdraw + self.close_profit) #原来计算的是错的，这里进行调整，
        self.pre_balance=self.balance
        self.static_balance = self.pre_balance

        self.close_profit = 0
        self.deposit = 0  # 入金
        self.withdraw = 0  # 出金
        self.premium = 0
        self.money += self.frozen_margin

        self.orders = {}
        self.frozen = {}
        self.trades = {}
        self.transfers = {}
        self.event = {}
        self.event_id = 0

        for item in self.positions.values():
            item.settle()

        # sell first >> second buy ==> for make sure have enough cash
        buy_order_sche = []
        for order in self.schedule.values():
            if order['towards'] > 0:
                # buy order
                buy_order_sche.append(order)
            else:
                self.send_order(order['code'], order['amount'],
                                order['price'], order['towards'], order['order_id'])
        for order in buy_order_sche:
            self.send_order(order['code'], order['amount'],
                            order['price'], order['towards'], order['order_id'])
        self.schedule = {}

    def send_order(self, code: str, amount: float, price: float, towards: int, order_id: str = '', datetime: str = ''):
        if datetime:
            self.on_price_change(code, price, datetime)
        order_id = str(uuid.uuid4()) if order_id == '' else order_id
        if self.order_check(code, amount, price, towards, order_id):
            self.log("order check success")
            direction, offset = parse_orderdirection(towards)
            self.event_id += 1
            order = {
                "account_cookie": self.user_id,
                "user_id": self.user_id,
                "instrument_id": code,
                "towards": int(towards),
                "exchange_id": self.market_preset.get_exchange(code),
                "order_time": self.dtstr,
                "volume": int(amount),
                "price": float(price),
                "order_id": order_id,
                "seqno": self.event_id,
                "direction": direction,
                "offset": offset,
                "volume_orign": int(amount),
                "price_type": "LIMIT",
                "limit_price": float(price),
                "time_condition": "GFD",
                "volume_condition": "ANY",
                "insert_date_time": self.transform_dt(self.dtstr),
                'order_time': self.dtstr,
                "exchange_order_id": str(uuid.uuid4()),
                "status": "ALIVE",
                "volume_left": int(amount),
                "last_msg": "已报"
            }
            self.orders[order_id] = order
            self.log('下单成功 {}'.format(order_id))
            if self.model != 'BACKTEST':
                self.sync()
            self.on_ordersend(order)
            return order
        else:
            self.log(RuntimeError("ORDER CHECK FALSE: {}".format(code)))
            return False