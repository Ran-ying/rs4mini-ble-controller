#import "RSSDKPanel.h"
#import "RSSDKActions.h"

@interface RSSDKPanel ()
@property(nonatomic,weak) RSGimbal *gimbal;
@property(nonatomic,strong) NSPopUpButton *group;
@property(nonatomic,strong) NSPopUpButton *operation;
@property(nonatomic,strong) NSButton *sourceButton;
@property(nonatomic,strong) NSButton *allowWrite;
@property(nonatomic,strong) NSButton *execute;
@property(nonatomic,strong) NSButton *degreeButton;
@property(nonatomic,strong) NSTextField *sourceLabel;
@property(nonatomic,strong) NSTextField *detail;
@property(nonatomic,strong) NSTextField *timeout;
@property(nonatomic,strong) NSStackView *form;
@property(nonatomic,strong) NSMutableDictionary<NSString *,NSControl *> *inputs;
@property(nonatomic,strong) NSTextView *results;
@property(nonatomic,strong) NSTextView *statuses;
@property(nonatomic,strong) NSArray *visibleOperations;
@property(nonatomic,strong) NSTabView *tabs;
@property(nonatomic) BOOL lastReady;
@property(nonatomic) BOOL pending;
@end

@implementation RSSDKPanel
static NSTextField *Text(NSString *s) { NSTextField *v=[NSTextField wrappingLabelWithString:s];v.font=[NSFont systemFontOfSize:12];return v; }
static NSScrollView *Viewer(NSTextView **output) {
    NSScrollView *scroll=[NSScrollView new];scroll.hasVerticalScroller=YES;scroll.autohidesScrollers=YES;scroll.borderType=NSBezelBorder;
    NSTextView *view=[[NSTextView alloc]initWithFrame:NSMakeRect(0,0,540,220)];view.editable=NO;view.selectable=YES;view.font=[NSFont monospacedSystemFontOfSize:11 weight:NSFontWeightRegular];view.autoresizingMask=NSViewWidthSizable;view.verticallyResizable=YES;view.horizontallyResizable=NO;view.textContainer.widthTracksTextView=YES;scroll.documentView=view;*output=view;return scroll;
}
- (instancetype)initWithFrame:(NSRect)frame gimbal:(RSGimbal *)gimbal {
    if(!(self=[super initWithFrame:frame]))return nil;
    self.gimbal=gimbal;self.inputs=[NSMutableDictionary dictionary];
    NSStackView *stack=[NSStackView new];stack.orientation=NSUserInterfaceLayoutOrientationVertical;stack.alignment=NSLayoutAttributeLeading;stack.spacing=10;stack.translatesAutoresizingMaskIntoConstraints=NO;[self addSubview:stack];
    [NSLayoutConstraint activateConstraints:@[[stack.leadingAnchor constraintEqualToAnchor:self.leadingAnchor constant:18],[stack.trailingAnchor constraintEqualToAnchor:self.trailingAnchor constant:-18],[stack.topAnchor constraintEqualToAnchor:self.topAnchor constant:18],[stack.bottomAnchor constraintEqualToAnchor:self.bottomAnchor constant:-18]]];
    NSTextField *title=Text(@"设备 SDK");title.font=[NSFont systemFontOfSize:21 weight:NSFontWeightSemibold];[stack addArrangedSubview:title];
    [stack addArrangedSubview:Text(@"使用同一个 RSGimbal 和蓝牙连接。App 来源能力已封装，本机效果待验；原生参数查询会先停止主机运动。")];
    self.sourceButton=[NSButton buttonWithTitle:@"启用 ronin-2.2.2 来源" target:self action:@selector(selectSource:)];[stack addArrangedSubview:self.sourceButton];
    self.sourceLabel=Text(@"来源尚未选择");[stack addArrangedSubview:self.sourceLabel];
    self.group=[NSPopUpButton new];NSMutableArray *groups=[NSMutableArray array];for(NSDictionary *row in RSSDKOperations())if(![groups containsObject:row[@"group"]])[groups addObject:row[@"group"]];[self.group addItemsWithTitles:groups];self.group.target=self;self.group.action=@selector(groupChanged:);[stack addArrangedSubview:self.group];
    self.operation=[NSPopUpButton new];self.operation.target=self;self.operation.action=@selector(operationChanged:);[stack addArrangedSubview:self.operation];
    self.detail=Text(@"");[stack addArrangedSubview:self.detail];
    self.form=[NSStackView new];self.form.orientation=NSUserInterfaceLayoutOrientationVertical;self.form.alignment=NSLayoutAttributeLeading;self.form.spacing=6;[stack addArrangedSubview:self.form];
    NSStackView *timeoutRow=[NSStackView new];timeoutRow.spacing=12;[timeoutRow addArrangedSubview:Text(@"请求超时（毫秒）")];self.timeout=[NSTextField new];self.timeout.stringValue=@"3000";[self.timeout.widthAnchor constraintEqualToConstant:100].active=YES;[timeoutRow addArrangedSubview:self.timeout];[stack addArrangedSubview:timeoutRow];
    self.allowWrite=[NSButton checkboxWithTitle:@"允许本次设备写入 / 触发请求" target:self action:@selector(writeChanged:)];[stack addArrangedSubview:self.allowWrite];
    NSStackView *buttons=[NSStackView new];buttons.spacing=12;
    self.execute=[NSButton buttonWithTitle:@"执行所选操作" target:self action:@selector(run:)];[buttons addArrangedSubview:self.execute];
    NSButton *stop=[NSButton buttonWithTitle:@"停止 / 取消主机任务" target:self action:@selector(stop:)];[buttons addArrangedSubview:stop];
    NSButton *keys=[NSButton buttonWithTitle:@"查看订阅键" target:self action:@selector(showKeys:)];[buttons addArrangedSubview:keys];self.degreeButton=[NSButton buttonWithTitle:@"原始 degree-info" target:self action:@selector(degreeInfo:)];[buttons addArrangedSubview:self.degreeButton];[stack addArrangedSubview:buttons];
    self.tabs=[NSTabView new];NSTextView *result,*status;
    NSTabViewItem *ri=[[NSTabViewItem alloc]initWithIdentifier:@"results"];ri.label=@"请求与结果";ri.view=Viewer(&result);self.results=result;[self.tabs addTabViewItem:ri];
    NSTabViewItem *si=[[NSTabViewItem alloc]initWithIdentifier:@"statuses"];si.label=@"被动状态";si.view=Viewer(&status);self.statuses=status;[self.tabs addTabViewItem:si];
    [stack addArrangedSubview:self.tabs];[self.tabs.heightAnchor constraintGreaterThanOrEqualToConstant:150].active=YES;
    for(NSView *view in stack.arrangedSubviews) if(view!=title && view!=timeoutRow && view!=buttons && view!=self.sourceButton)[view.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active=YES;
    [self.tabs setContentHuggingPriority:1 forOrientation:NSLayoutConstraintOrientationVertical];
    [self append:@"未发送请求。请选择操作并填写表单；读取结果和请求值分开显示。"];
    [self groupChanged:nil];[self refresh];return self;
}
- (NSDictionary *)selected { NSInteger i=self.operation.indexOfSelectedItem;return i>=0&&i<(NSInteger)self.visibleOperations.count?self.visibleOperations[i]:nil; }
- (void)append:(NSString *)text {
    NSString *stamp=[NSDateFormatter localizedStringFromDate:NSDate.date dateStyle:NSDateFormatterNoStyle timeStyle:NSDateFormatterMediumStyle];
    NSString *all=[self.results.string stringByAppendingFormat:@"\n[%@] %@\n",stamp,text];
    if(all.length>120000)all=[all substringFromIndex:all.length-100000];self.results.string=all;[self.results scrollRangeToVisible:NSMakeRange(all.length,0)];
}
- (void)groupChanged:(id)sender {
    NSMutableArray *rows=[NSMutableArray array];[self.operation removeAllItems];for(NSDictionary *row in RSSDKOperations())if([row[@"group"] isEqual:self.group.titleOfSelectedItem]){[rows addObject:row];[self.operation addItemWithTitle:row[@"title"]];}self.visibleOperations=rows;[self operationChanged:nil];
}
- (void)operationChanged:(id)sender {
    for(NSView *v in [self.form.arrangedSubviews copy]){[self.form removeArrangedSubview:v];[v removeFromSuperview];}[self.inputs removeAllObjects];
    NSDictionary *op=[self selected];self.detail.stringValue=op[@"detail"]?:@"";self.allowWrite.state=NSControlStateValueOff;
    for(NSDictionary *f in op[@"fields"]) {
        NSStackView *row=[NSStackView new];row.spacing=10;NSTextField *label=Text(f[@"label"]);[label.widthAnchor constraintEqualToConstant:160].active=YES;[row addArrangedSubview:label];NSControl *input;
        if(f[@"choices"]||[f[@"kind"] isEqual:@"bool"]){NSPopUpButton *p=[NSPopUpButton new];[p addItemWithTitle:[f[@"required"] boolValue]?@"请选择…":@"不指定 / 不修改"];for(NSString *choice in f[@"choices"]?:@[@"true",@"false"]){NSString *name=@{@"true":@"是 / 开启",@"false":@"否 / 关闭",@"pitch":@"Pitch（俯仰）",@"roll":@"Roll（横滚）",@"yaw":@"Yaw（航向）",@"speed":@"速度",@"acceleration":@"加速度",@"deadZone":@"死区",@"smoothing":@"平滑",@"stiffness":@"刚度",@"strength":@"强度",@"gyroFiltering":@"陀螺滤波",@"preControl":@"预控制",@"track":@"轨迹",@"timelapse":@"延时",@"panorama":@"全景"}[choice]?:choice;[p addItemWithTitle:name];p.lastItem.representedObject=choice;p.lastItem.toolTip=choice;}input=p;}
        else {NSTextField *p=[NSTextField new];p.placeholderString=[f[@"kind"] isEqual:@"keys"]?@"输入命名键，逗号分隔":[NSString stringWithFormat:@"%@..%@（源范围）",f[@"min"],f[@"max"]];input=p;}
        [input.widthAnchor constraintEqualToConstant:320].active=YES;[row addArrangedSubview:input];[self.form addArrangedSubview:row];self.inputs[f[@"key"]]=input;
    }
    [self refresh];
}
- (void)writeChanged:(id)sender { [self refresh]; }
- (void)selectSource:(id)sender {
    if(self.pending||self.gimbal.busy)return;
    if([self.gimbal useAppProfile:@"ronin-2.2.2"]){self.allowWrite.state=NSControlStateValueOff;[self append:@"已显式选择 ronin-2.2.2 来源；不是设备支持确认，未自动查询或写入。"];}
    [self refresh];
}
- (void)refresh {
    BOOL ready=self.gimbal.ready,busy=self.gimbal.busy||self.pending,profile=[self.gimbal.appProfile isEqual:@"ronin-2.2.2"];
    if(self.lastReady&&!ready){self.allowWrite.state=NSControlStateValueOff;[self append:@"连接已断开；不重放请求，状态缓存已清空。"];}
    self.lastReady=ready;
    self.sourceLabel.stringValue=[NSString stringWithFormat:@"%@ · %@",profile?@"来源：ronin-2.2.2":@"来源：未选择",!ready?@"未连接":busy?@"操作中":@"已连接 / 空闲"];
    self.degreeButton.enabled=ready&&!busy;self.sourceButton.enabled=!busy&&!profile;self.group.enabled=self.operation.enabled=!busy;
    for(NSControl *v in self.inputs.allValues)v.enabled=!busy;
    self.allowWrite.enabled=ready&&profile&&!busy&&[[self selected][@"write"] boolValue];
    self.execute.enabled=ready&&!busy&&profile&&(![[self selected][@"write"] boolValue]||self.allowWrite.state==NSControlStateValueOn);
    NSString *snapshot=RSSDKDisplay(RSSDKStatusSnapshot(self.gimbal));if(![self.statuses.string isEqual:snapshot])self.statuses.string=snapshot;
}
- (void)run:(id)sender {
    NSDictionary *op=[self selected];BOOL writes=[op[@"write"] boolValue];
    if(self.pending||!self.gimbal.ready||self.gimbal.busy||![self.gimbal.appProfile isEqual:@"ronin-2.2.2"]||(writes&&self.allowWrite.state!=NSControlStateValueOn))return;
    NSMutableDictionary *raw=[NSMutableDictionary dictionary];for(NSString *key in self.inputs){NSControl *input=self.inputs[key];if([input isKindOfClass:NSPopUpButton.class]){NSPopUpButton *p=(id)input;if(p.indexOfSelectedItem>0)raw[key]=p.selectedItem.representedObject;}else raw[key]=input.stringValue;}
    NSError *error;NSDictionary *spec=RSSDKParseForm(op[@"id"],raw,&error);
    NSScanner *scan=[NSScanner scannerWithString:self.timeout.stringValue];double timeout;scan.charactersToBeSkipped=nil;
    if(!spec||![scan scanDouble:&timeout]||!scan.isAtEnd||!isfinite(timeout)||timeout<=0||timeout>60000){[self append:error.localizedDescription?:@"超时需为大于0且不超过60000的毫秒数"];return;}
    // Values and operation are captured before presenting a maintenance confirmation.
    NSDictionary *snapshot=[raw copy];NSString *identifier=[op[@"id"] copy],*title=[op[@"title"] copy];
    __weak typeof(self) weak=self;
    void (^perform)(void)=^{
        if(!weak)return;
        if(!weak.gimbal.ready||weak.gimbal.busy||weak.pending){[weak append:@"设备状态已改变，本次操作未发送。"];return;}
        weak.pending=YES;weak.allowWrite.state=NSControlStateValueOff;[weak append:[NSString stringWithFormat:@"请求：%@\n%@",title,RSSDKDisplay(spec)]];[weak refresh];
        RSSDKDispatch(weak.gimbal,identifier,snapshot,timeout,^(NSDictionary *reply,NSError *err){dispatch_async(dispatch_get_main_queue(),^{weak.pending=NO;[weak append:err?[NSString stringWithFormat:@"%@失败：%@",title,err.localizedDescription]:[NSString stringWithFormat:@"%@返回（不等同物理完成）：\n%@",title,RSSDKDisplay(reply)]];[weak refresh];});});
    };
    if([op[@"confirm"] boolValue]){NSAlert *alert=[NSAlert new];alert.messageText=title;alert.informativeText=[NSString stringWithFormat:@"%@\n\n请求参数：\n%@",op[@"detail"],RSSDKDisplay(spec)];[alert addButtonWithTitle:@"发送请求"];[alert addButtonWithTitle:@"取消"];[alert beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse response){weak.allowWrite.state=NSControlStateValueOff;[weak refresh];if(response==NSAlertFirstButtonReturn)perform();}];}else perform();
}
- (void)degreeInfo:(id)sender { if(!self.gimbal.ready||self.gimbal.busy||self.pending)return;[self append:@"发起原始 degree-info 查询（固定3秒截止；字段含义待验）。"];[self.gimbal requestDegreeInfo];[self refresh]; }
- (void)receiveMessage:(NSDictionary *)message { if([message[@"commandSet"] intValue]==4&&[message[@"commandId"] intValue]==30)[self append:[@"收到4:1E原始消息（非业务字段验收）：\n" stringByAppendingString:RSSDKDisplay(message)]]; }
- (void)stop:(id)sender { [self.gimbal stop];self.allowWrite.state=NSControlStateValueOff;[self append:@"已请求停止主机任务并发送中位；不等同固件校准/程序中止。"];[self refresh]; }
- (void)showKeys:(id)sender { [self append:[@"可用命名订阅键（查看不发送）：\n" stringByAppendingString:[self.gimbal.appParameterSubscriptionKeys componentsJoinedByString:@", "]]];[self.tabs selectTabViewItemAtIndex:0]; }
- (void)receiveStatus:(NSDictionary *)status { [self refresh]; }
@end
