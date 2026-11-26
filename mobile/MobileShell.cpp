// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 by-jsk. Independent mobile interface for Stellarium.
#include "MobileShell.hpp"
#include "MobileVersion.hpp"
#include "SkyGui.hpp"
#include "StelGuiItems.hpp"
#include "ConstellationMgr.hpp"
#include <algorithm>
#include "StelMainView.hpp"
#include "StelApp.hpp"
#include "StelCore.hpp"
#include "StelLocaleMgr.hpp"
#include "StelActionMgr.hpp"
#include "StelObjectMgr.hpp"
#include "StelObject.hpp"
#include "StelIniParser.hpp"
#include "StelMovementMgr.hpp"
#include "StelLocation.hpp"
#include "StelLocationMgr.hpp"
#include "StelModuleMgr.hpp"
#include "StelModule.hpp"
#include "StelTranslator.hpp"
#include <QtWidgets>
#include <QJsonArray>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QGeoPositionInfoSource>
#include <QGeoPositionInfo>
#include <QStandardPaths>
#include <QLocationPermission>
#include <QInputMethod>
#include <QTimeZone>
#include <QWindow>
#include <cmath>
#ifdef Q_OS_ANDROID
#include <QJniObject>
#include <QCoreApplication>
static QJniObject androidContext() { return QNativeInterface::QAndroidApplication::context(); }
#endif

namespace {
// [20261126 by jsk] 검은 하늘의 별자리 선·이름을 분리하며 적색 야간 셰이더에서도 밝기를 확보함.
const QString constellationLines = QStringLiteral("0.52,0.80,1.00");
const QString constellationNames = QStringLiteral("1.00,0.91,0.66");

// [20261126 by jsk] Stellarium 형식으로 읽어 쉼표가 포함된 색과 하늘 방향을 문자열로 보존함.
QSettings::SettingsMap readMobileSettings(const QString& path)
{
    QSettings::SettingsMap values;
    QFile file(path);
    if (file.open(QIODevice::ReadOnly)) {
        readStelIniFile(file, values);
    }
    return values;
}

#ifdef STELLAR_CI_FIXTURE
// [20261126 by jsk] Qt 화면의 버튼 중심을 Android 터치 좌표로 변환함.
void reportUpdateButton(const char* marker, QGraphicsProxyWidget* page, QPushButton* button)
{
    auto& view = StelMainView::getInstance();
    const auto center = button->mapTo(page->widget(), button->rect().center());
    const auto point = view.mapToGlobal(view.mapFromScene(page->mapToScene(center)));
    const auto ratio = view.devicePixelRatioF();
    qInfo().noquote() << marker << QJsonDocument(QJsonObject{
        {"x", qRound(point.x()*ratio)}, {"y", qRound(point.y()*ratio)}
    }).toJson(QJsonDocument::Compact);
}
#endif
}

void MobileShell::prepare()
{
    QCoreApplication::setApplicationName("StellarTouch");
    QCoreApplication::setApplicationVersion(STELLAR_VERSION_NAME);
    QCoreApplication::setOrganizationName("by-jsk");
    const auto config = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation) + "/config";
    QDir().mkpath(config);
    qputenv("STEL_USERDIR", config.toUtf8());
    const auto initial = readMobileSettings(config+"/config.ini");
    const int brightness=initial.value("mobile/nightBrightness",40).toInt();
    const bool night=initial.value("viewing/flag_night",true).toBool();
    qApp->setProperty("stellarNightBrightness",qBound(5,brightness,100)/100.0);
#ifdef Q_OS_ANDROID
    androidContext().callMethod<void>("setNightLighting","(ZIZ)V",jboolean(night),jint(brightness),jboolean(initial.value("mobile/keepAwake",true).toBool()));
#endif
}

MobileShell::MobileShell(QGraphicsWidget* parent, SkyGui* skyGui) : QObject(parent), root(parent), sky(skyGui)
{
    QFile file("assets:/mobile-i18n.json");
    if (file.open(QIODevice::ReadOnly)) strings = QJsonDocument::fromJson(file.readAll()).object();
    auto& app = StelApp::getInstance();
    auto* settings = app.getSettings();
    showInfo = settings->value("mobile/showObjectInfo", true).toBool();
    auto constellations = GETSTELMODULE(ConstellationMgr);
    // [20261126 by jsk] 기존 어두운 설정을 한 번 교체하고 이후 사용자가 선택한 선 표시 여부를 보존함.
    const bool firstPalette = !settings->value("mobile/highContrastConstellations", false).toBool();
    if (firstPalette || settings->value("color/const_lines_color").toString().isEmpty()) {
        constellations->setLinesColor(Vec3f(constellationLines));
        constellations->setLabelsColor(Vec3f(constellationNames));
        settings->setValue("color/const_lines_color", constellationLines);
        settings->setValue("color/const_names_color", constellationNames);
    }
    if (firstPalette) {
        constellations->setFlagLines(true);
        settings->setValue("viewing/flag_constellation_drawing", true);
        settings->setValue("mobile/highContrastConstellations", true);
    }
    applyLanguage();
    toolbar();
    connect(&app.getStelObjectMgr(), &StelObjectMgr::selectedObjectChanged, this, [this] {
        infoDismissed = false;
        refreshInfo();
    });
    lighting();
    StelMainView::getInstance().installEventFilter(this);
    connect(&StelApp::getInstance(), &StelApp::languageChanged, this, [this] { toolbar(); });
    connect(&StelApp::getInstance(), &StelApp::visionNightModeChanged, this, [this] {lighting();nightButton->setChecked(StelApp::getInstance().getVisionModeNight());StelApp::getInstance().getSettings()->sync();});
    connect(qApp,&QGuiApplication::applicationStateChanged,this,[](Qt::ApplicationState state){if(state!=Qt::ApplicationActive)StelApp::getInstance().getSettings()->sync();});
    layout();
#if QT_VERSION >= QT_VERSION_CHECK(6,9,0)
    if(auto window=StelMainView::getInstance().windowHandle())connect(window,&QWindow::safeAreaMarginsChanged,this,[this]{layout();});
#endif
    qInfo() << "STELLAR_TOUCH_READY";
#ifdef Q_OS_ANDROID
#ifdef STELLAR_CI_FIXTURE
    if(androidContext().callMethod<jboolean>("isUpgradeTest")) {
        // [20261126 by jsk] 업데이트 페이지는 실제 설정 버튼 입력으로 진입하도록 시험 경로를 변경함.
        QTimer::singleShot(2000, this, [this]{ this->settings(); });
        return;
    }
#endif
    if(androidContext().callMethod<jboolean>("isSmokeTest"))
        QTimer::singleShot(10000,this,[this]{smokeTest();});
#endif
}

QString MobileShell::trm(const char* key) const
{
    const auto fallback = strings.value("en").toObject().value(key).toString(QString::fromUtf8(key));
    return strings.value(language).toObject().value(key).toString(fallback);
}

void MobileShell::applyLanguage()
{
    auto conf = StelApp::getInstance().getSettings();
    auto choice = conf->value("mobile/language", "system").toString();
    language = choice;
    if (choice == "system") {
        language = "en";
        for (const auto& tag : QLocale::system().uiLanguages()) {
            const auto base = tag.left(2).toLower();
            if (QStringList{"ko","en","ja","zh","es","ru"}.contains(base)) { language=base; break; }
        }
    }
    if (!strings.contains(language)) language = "en";
    const auto upstream = language == "zh" ? QString("zh_CN") : language;
    conf->setValue("localization/app_locale", upstream);
    conf->sync();
    StelApp::getInstance().getLocaleMgr().setAppLanguage(upstream);
    auto region = conf->value("mobile/region", "system").toString();
    QLocale format = region == "system" ? QLocale::system() : QLocale("en_" + region);
    // Keep numeric parser locale untouched; format only user-facing date widgets with this locale.
    qApp->setProperty("stellarRegionLocale", format.name());
}

void MobileShell::toolbar()
{
    for (auto proxy : {bar, bottomBar, menuSwitch, infoClose}) {
        if (proxy) { proxy->hide(); proxy->deleteLater(); }
    }
    const QString style = "QWidget{background:#101a28;color:#f1f5ff;} QScrollArea{border:0;}"
        "QToolButton{border:1px solid #60768e;border-radius:7px;padding:3px;}"
        "QToolButton:checked{background:#435975;border-color:#c5dfff;}";
    auto proxyFor = [this, &style](QWidget* widget) {
        widget->setStyleSheet(style + QString("QToolButton{font-size:%1px;}").arg(qBound(12, StelApp::getInstance().getScreenFontSize(), 30)));
        auto proxy = new QGraphicsProxyWidget(root);
        proxy->setWidget(widget);
        proxy->setZValue(250);
        return proxy;
    };
    auto button = [this](QString label, QString description, const std::function<void()>& callback) {
        auto b = new QToolButton;
        b->setText(label);
        b->setAccessibleName(description);
        b->setToolTip(description);
        b->setMinimumSize(44,44);
        connect(b, &QToolButton::clicked, this, callback);
        return b;
    };
    auto row = [&proxyFor](QGraphicsProxyWidget*& proxy) {
        auto scroll = new QScrollArea;
        auto inner = new QWidget;
        auto box = new QHBoxLayout(inner);
        box->setContentsMargins(3,2,3,2);
        box->setSpacing(4);
        box->setSizeConstraint(QLayout::SetMinAndMaxSize);
        scroll->setWidget(inner);
        scroll->setWidgetResizable(true);
        scroll->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
        scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);
        QScroller::grabGesture(scroll->viewport(), QScroller::TouchGesture);
        proxy = proxyFor(scroll);
        return box;
    };
    auto top = row(bar);
    nightButton = button("R", trm("night"), [] {
        auto& app = StelApp::getInstance();
        app.setVisionModeNight(!app.getVisionModeNight());
    });
    nightButton->setCheckable(true);
    nightButton->setChecked(StelApp::getInstance().getVisionModeNight());
    top->addWidget(nightButton);
    top->addWidget(button("A+", trm("fontUp"), [this]{changeFont(2);}));
    top->addWidget(button("A−", trm("fontDown"), [this]{changeFont(-2);}));
    auto info = button(trm("objectInfo"), trm("objectInfo"), [this]{
        showInfo = !showInfo;
        infoDismissed = false;
        StelApp::getInstance().getSettings()->setValue("mobile/showObjectInfo", showInfo);
        refreshInfo();
    });
    info->setCheckable(true);
    info->setChecked(showInfo);
    top->addWidget(info);
    top->addWidget(button("?", trm("help"), [this]{help();}));
    top->addWidget(button("ⓘ", trm("about"), [this]{about();}));
    top->addWidget(button("⚙", trm("settings"), [this]{settings();}));

    auto bottom = row(bottomBar);
    auto add = [bottom](QToolButton* b) {
        b->setMinimumSize(80,54);
        bottom->addWidget(b);
    };
    add(button(trm("search"), trm("search"), [this]{search();}));
    add(button(trm("time"), trm("time"), [this]{time();}));
    add(button(trm("location"), trm("location"), [this]{location();}));
    add(button(trm("tools"), trm("tools"), [this]{tools();}));
    auto items = sky->bottomBar->childItems();
    std::stable_sort(items.begin(), items.end(), [](auto a, auto b){ return a->x() < b->x(); });
    for (auto item : items) {
        auto original = dynamic_cast<StelButton*>(item);
        if (!original || !original->mobileAction()) continue;
        auto a = original->mobileAction();
        const QString label = a->getText();
        auto b = button(label, label, [action=QPointer<StelAction>(a)]{if (action) action->trigger();});
        b->setCheckable(a->isCheckable());
        if (a->isCheckable()) {
            b->setChecked(a->isChecked());
            connect(a, &StelAction::toggled, b, &QToolButton::setChecked);
        }
        add(b);
    }
    menuSwitch = proxyFor(button({}, {}, [this]{
        menusVisible = !menusVisible;
        if (!menusVisible && panel) panel->hide();
        layout();
    }));
    infoClose = proxyFor(button("×", trm("close"), [this]{infoDismissed = true; refreshInfo();}));
    layout();
}

void MobileShell::changeFont(int delta)
{
    auto& app = StelApp::getInstance();
    app.setScreenFontSize(qBound(10, app.getScreenFontSize()+delta, 36));
    auto constellations = GETSTELMODULE(ConstellationMgr);
    constellations->setFontSize(qBound(10, constellations->getFontSize()+delta, 36));
    toolbar();
    if (panel) {
        panel->widget()->setStyleSheet(panelStyle());
        layout();
    }
}

void MobileShell::refreshInfo()
{
    const bool visible = showInfo && !infoDismissed && !StelApp::getInstance().getStelObjectMgr().getSelectedObject().isEmpty();
    sky->infoPanel->setVisible(visible);
    infoClose->setVisible(visible);
}

void MobileShell::layout()
{
    auto& view = StelMainView::getInstance();
    QMargins safe;
#if QT_VERSION >= QT_VERSION_CHECK(6,9,0)
    if (auto window = view.windowHandle()) safe = window->safeAreaMargins();
#endif
    const QRect area = view.rect().marginsRemoved(safe).adjusted(4,4,-4,-4);
    auto toggle = static_cast<QToolButton*>(menuSwitch->widget());
    const auto label = trm(menusVisible ? "hideMenus" : "showMenus");
    toggle->setText(label);
    toggle->setAccessibleName(label);
    menuSwitch->resize(toggle->sizeHint());
    menuSwitch->setPos(area.right()+1-menuSwitch->size().width(), area.top());
    const int topHeight = 52 + bar->widget()->style()->pixelMetric(QStyle::PM_ScrollBarExtent);
    const int bottomHeight = topHeight+10;
    bar->setGeometry(QRectF(area.left(), area.top(), qMax(1, int(menuSwitch->x())-area.left()-4), topHeight));
    bottomBar->setGeometry(QRectF(area.left(), area.bottom()+1-bottomHeight, area.width(), bottomHeight));
    bar->setVisible(menusVisible);
    bottomBar->setVisible(menusVisible);
    sky->bottomBar->hide();
    sky->buttonBarsFrame->hide();
    sky->autoHidebts->setVisible(menusVisible);
    sky->leftBar->setVisible(menusVisible);
    const int infoTop = area.top() + (menusVisible ? topHeight+2 : 0);
    infoClose->setPos(area.left(), infoTop);
    qApp->setProperty("stellarInfoTop", infoTop+48);
    qApp->setProperty("stellarInfoLeft", area.left());
    qApp->setProperty("stellarInfoWidth", area.width());
    sky->updateInfoPanelPos();
    refreshInfo();
    if (panel) panel->setGeometry(QRectF(area.left(), area.top()+topHeight, area.width(), qMax(1,area.height()-topHeight-bottomHeight)));
}

bool MobileShell::eventFilter(QObject* watched, QEvent* event)
{
    if(event->type()==QEvent::Resize) QTimer::singleShot(0,this,[this]{layout();});
    if(event->type()==QEvent::KeyPress && static_cast<QKeyEvent*>(event)->key()==Qt::Key_Back && panel && panel->isVisible()) {panel->hide(); return true;}
    return QObject::eventFilter(watched,event);
}

void MobileShell::fitDialog(QWidget* dialog, QGraphicsProxyWidget* proxy)
{
    if(!dialog || !proxy) return;
    if(!dialog->property("stellarScroll").toBool()) {
        auto old = dialog->layout();
        if(old) {
            auto inner=new QWidget; inner->setLayout(old);
            auto scroll=new QScrollArea; scroll->setWidget(inner); scroll->setWidgetResizable(true);
            QScroller::grabGesture(scroll->viewport(),QScroller::TouchGesture);
            auto box=new QVBoxLayout(dialog); box->setContentsMargins(0,0,0,0); box->addWidget(scroll);
            box->setSizeConstraint(QLayout::SetNoConstraint);
            dialog->setMinimumSize(0,0); dialog->setProperty("stellarScroll",true);
        }
    }
    const auto s=StelMainView::getInstance().size();
    QMargins safe;
#if QT_VERSION >= QT_VERSION_CHECK(6,9,0)
    if(auto window=StelMainView::getInstance().windowHandle())safe=window->safeAreaMargins();
#endif
    dialog->resize(qMax(240,s.width()-16-safe.left()-safe.right()),qMax(120,s.height()-136-safe.top()-safe.bottom()));
    proxy->setPos(safe.left()+8,safe.top()+120); proxy->setZValue(260);
}

QString MobileShell::panelStyle() const
{
    const int size = qBound(12, StelApp::getInstance().getScreenFontSize(), 30);
    return QString("QWidget{background:#111c2c;color:#eff5ff;font-size:%1px;} QPushButton,QToolButton,QComboBox,QLineEdit,QDateTimeEdit,QDoubleSpinBox{min-height:44px;border:1px solid #3c526b;border-radius:8px;padding:4px;background:#182b42;color:#eff5ff;} QPushButton:checked{background:#375f86;} QLabel{background:transparent;} QLabel#pageTitle{font-size:%2px;font-weight:bold;} QScrollArea{border:0;}").arg(size).arg(size+4);
}

void MobileShell::page(const char* title)
{
    currentPage=QString::fromUtf8(title);
    if(panel) { panel->hide(); panel->deleteLater(); panel=nullptr; }
    auto frame=new QWidget;
    frame->setStyleSheet(panelStyle());
    auto outer=new QVBoxLayout(frame);
    auto header=new QHBoxLayout;
    auto heading=new QLabel(trm(title)); heading->setObjectName("pageTitle"); header->addWidget(heading,1);
    auto close=new QToolButton; close->setText("×"); close->setAccessibleName(trm("close")); connect(close,&QToolButton::clicked,this,[this]{panel->hide(); StelMainView::getInstance().focusSky();}); header->addWidget(close);
    outer->addLayout(header);
    auto scroll=new QScrollArea; scroll->setWidgetResizable(true);
    content=new QWidget; body=new QVBoxLayout(content); body->setAlignment(Qt::AlignTop); body->setSpacing(10);
    scroll->setWidget(content); QScroller::grabGesture(scroll->viewport(),QScroller::TouchGesture); outer->addWidget(scroll);
    panel=new QGraphicsProxyWidget(root); panel->setWidget(frame); panel->setZValue(255); layout();
}
QPushButton* MobileShell::addButton(const QString& label,const std::function<void()>& cb) {auto b=new QPushButton(label); b->setAccessibleName(label); connect(b,&QPushButton::clicked,this,cb); body->addWidget(b);return b;}
void MobileShell::addText(const QString& text) {auto l=new QLabel(text); l->setWordWrap(true); l->setTextFormat(Qt::PlainText); l->setTextInteractionFlags(Qt::TextSelectableByMouse); body->addWidget(l);}
void MobileShell::action(const QString& id) {if(auto a=StelApp::getInstance().getStelActionManager()->findAction(id)) {if(panel)panel->hide(); a->trigger();}}
void MobileShell::settings() {
    page("settings");addButton("?  "+trm("help"),[this]{help();});addButton("ⓘ  "+trm("about"),[this]{about();});addButton("文  "+trm("languages"),[this]{languages();});
    const QPointer<QGraphicsProxyWidget> settingsPage = panel;
    // [20261126 by jsk] 설정 버튼의 터치 해제가 끝난 뒤 기존 화면을 교체함.
    auto update = addButton(trm("update"), [this, settingsPage] {
        QTimer::singleShot(0, this, [this, settingsPage] {
            if (settingsPage && settingsPage == panel && settingsPage->isVisible()) updates();
        });
    });
    QPixmap image(64,64);image.fill(Qt::transparent);
    {QPainter painter(&image);painter.setRenderHint(QPainter::Antialiasing);painter.setPen(QPen(QColor("#eff5ff"),5,Qt::SolidLine,Qt::RoundCap,Qt::RoundJoin));painter.drawArc(QRectF(12,12,40,40),45*16,285*16);painter.drawLine(QPointF(48,10),QPointF(48,27));painter.drawLine(QPointF(48,27),QPointF(32,27));}
    update->setIcon(QIcon(image));update->setIconSize(QSize(24,24));addButton(trm("observing"),[this]{observing();});
#ifdef STELLAR_CI_FIXTURE
    if (androidContext().callMethod<jboolean>("isUpgradeTest")) {
        QTimer::singleShot(500, this, [this, settingsPage, button=QPointer<QPushButton>(update)] {
            if (button && settingsPage == panel && settingsPage->isVisible()) {
                reportUpdateButton("STELLAR_UPDATE_SETTINGS_BUTTON", settingsPage, button);
            }
        });
    }
#endif
}
void MobileShell::help() {page("help"); addText(trm("guide"));}
void MobileShell::about() {page("about");addText(QString("Stellar Touch %1").arg(STELLAR_VERSION_NAME)); addText(trm("description")); addText(trm("license")); addButton(trm("source"),[]{QDesktopServices::openUrl(QUrl("https://github.com/by-jsk/stellarium-android"));}); addButton(trm("desktopSettings"),[this]{action("actionShow_Configuration_Window_Global");});}
void MobileShell::languages()
{
    page("languages"); auto conf=StelApp::getInstance().getSettings();
    addText(trm("language")); auto lang=new QComboBox; lang->addItem(trm("deviceDefault"),"system");
    const QStringList codes{"ko","en","ja","zh","es","ru"}, names{"한국어","English","日本語","中文","Español","Русский"};
    for(int i=0;i<codes.size();++i)lang->addItem(names[i],codes[i]);
    lang->setCurrentIndex(qMax(0,lang->findData(conf->value("mobile/language","system")))); lang->setAccessibleName(trm("language")); body->addWidget(lang);
    addText(trm("region")); auto region=new QComboBox; region->addItem(trm("deviceDefault"),"system");
    QMap<QString,QString> regions;
    for(const auto& locale:QLocale::matchingLocales(QLocale::AnyLanguage,QLocale::AnyScript,QLocale::AnyTerritory)) {
        const auto code=locale.name().section('_',-1); if(code.size()==2)regions.insert(code,QLocale::territoryToString(locale.territory()));
    }
    for(auto i=regions.cbegin();i!=regions.cend();++i) {
        auto label=i.value();
#ifdef Q_OS_ANDROID
        label=androidContext().callObjectMethod("countryName","(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",QJniObject::fromString(i.key()).object<jstring>(),QJniObject::fromString(language).object<jstring>()).toString();
#endif
        region->addItem(i.key()+" · "+label,i.key());
    }
    region->setCurrentIndex(qMax(0,region->findData(conf->value("mobile/region","system")))); region->setAccessibleName(trm("region")); body->addWidget(region);
    addButton(trm("save"),[this,lang,region,conf]{conf->setValue("mobile/language",lang->currentData());conf->setValue("mobile/region",region->currentData());applyLanguage();languages();});
    addButton(trm("resetDefaults"),[this,conf]{conf->remove("mobile/language");conf->remove("mobile/region");applyLanguage();languages();});
}
void MobileShell::search()
{
    page("search"); auto input=new QLineEdit; input->setPlaceholderText(trm("searchHint")); input->setAccessibleName(trm("search")); body->addWidget(input);
    auto status=new QLabel; status->setWordWrap(true); body->addWidget(status);
    auto find=[this,input,status]{auto mgr=&StelApp::getInstance().getStelObjectMgr();const auto query=input->text().trimmed(); if(query.isEmpty())return;
        if(mgr->findAndSelectI18n(query)||mgr->findAndSelect(query)){auto selected=mgr->getSelectedObject();if(!selected.isEmpty()){auto movement=StelApp::getInstance().getCore()->getMovementMgr();movement->moveToObject(selected.first());movement->setFlagTracking(true);}panel->hide();QGuiApplication::inputMethod()->hide();}
        else status->setText(trm("notFound"));};
    addButton(trm("search"),find); connect(input,&QLineEdit::returnPressed,this,find);
    auto matches=new QListWidget;matches->setUniformItemSizes(true);matches->setMinimumHeight(160);matches->setAccessibleName(trm("search"));matches->setStyleSheet("QListWidget::item{min-height:44px;}");body->addWidget(matches);
    auto debounce=new QTimer(input);debounce->setSingleShot(true);debounce->setInterval(150);
    connect(input,&QLineEdit::textEdited,debounce,[debounce]{debounce->start();});
    connect(debounce,&QTimer::timeout,matches,[input,matches]{matches->clear();const auto query=input->text().trimmed();if(query.size()<2)return;for(const auto& match:StelApp::getInstance().getStelObjectMgr().listMatchingObjects(query,8))matches->addItem(match.first);});
    connect(matches,&QListWidget::itemClicked,this,[input,find](QListWidgetItem* item){input->setText(item->text());find();});
    addButton(trm("advanced"),[this]{action("actionShow_Search_Window_Global");});
}
void MobileShell::time()
{
    page("time"); auto core=StelApp::getInstance().getCore();
    QTimeZone zone(core->getCurrentTimeZone().toUtf8());
    if(!zone.isValid())zone=QTimeZone::fromSecondsAheadOfUtc(qRound(core->getUTCOffset(core->getJD())*3600));
    addText(trm("timezone")+": "+QString::fromUtf8(zone.id()));
    auto input=new QDateTimeEdit;input->setTimeZone(zone);input->setDateTime(QDateTime::fromMSecsSinceEpoch(qint64((core->getJD()-2440587.5)*86400000.0),zone)); input->setDisplayFormat("yyyy-MM-dd HH:mm:ss"); input->setLocale(QLocale(qApp->property("stellarRegionLocale").toString())); input->setAccessibleName(trm("time")); body->addWidget(input);
    addButton(trm("applyTime"),[this,input,core]{core->setJD(input->dateTime().toUTC().toMSecsSinceEpoch()/86400000.0+2440587.5);panel->hide();});
    addButton(trm("now"),[this,core]{core->setJD(QDateTime::currentMSecsSinceEpoch()/86400000.0+2440587.5);core->setTimeRate(1.0/86400.0);panel->hide();});
    addButton(trm("pause"),[core]{core->setTimeRate(0);}); addButton("1×",[core]{core->setTimeRate(1.0/86400.0);}); addButton("100×",[core]{core->setTimeRate(100.0/86400.0);}); addButton("−100×",[core]{core->setTimeRate(-100.0/86400.0);});
    addButton(trm("advanced"),[this]{action("actionShow_DateTime_Window_Global");});
}
void MobileShell::location()
{
    page("location");
    addText(trm("locationHint"));
    auto core=StelApp::getInstance().getCore();
    const auto current=core->getCurrentLocation();
    auto lat=new QDoubleSpinBox;lat->setRange(-90,90);lat->setDecimals(5);lat->setValue(current.getLatitude());lat->setAccessibleName(trm("latitude"));
    auto lon=new QDoubleSpinBox;lon->setRange(-180,180);lon->setDecimals(5);lon->setValue(current.getLongitude());lon->setAccessibleName(trm("longitude"));
    auto altitude=new QSpinBox;altitude->setRange(-1000,100000);altitude->setValue(current.altitude);altitude->setAccessibleName(trm("altitude"));
    auto zone=new QComboBox;zone->setAccessibleName(trm("timezone"));
    for(const auto& id:QTimeZone::availableTimeZoneIds())zone->addItem(QString::fromUtf8(id),QString::fromUtf8(id));
    int selected=zone->findData(core->getCurrentTimeZone());
    if(selected<0)selected=zone->findData(QString::fromUtf8(QTimeZone::systemTimeZoneId()));
    zone->setCurrentIndex(qMax(0,selected));
    QPointer<QDoubleSpinBox> latitude=lat,longitude=lon;
    QPointer<QSpinBox> elevation=altitude;
    QPointer<QComboBox> timezone=zone;
    auto locate=[this,latitude,longitude,elevation,timezone]{
        if(!latitude||!longitude||!elevation||!timezone)return;
        auto source=QGeoPositionInfoSource::createDefaultSource(this);
        if(!source){addText(trm("gpsError"));return;}
        connect(source,&QGeoPositionInfoSource::positionUpdated,this,[source,latitude,longitude,elevation,timezone](const QGeoPositionInfo& pos){
            if(latitude&&longitude&&elevation&&timezone){
                latitude->setValue(pos.coordinate().latitude());longitude->setValue(pos.coordinate().longitude());
                if(std::isfinite(pos.coordinate().altitude()))elevation->setValue(qRound(pos.coordinate().altitude()));
                const auto index=timezone->findData(QString::fromUtf8(QTimeZone::systemTimeZoneId()));if(index>=0)timezone->setCurrentIndex(index);
            }
            source->deleteLater();
        });
        auto failed=[this,source]{if(currentPage=="location")addText(trm("gpsError"));source->deleteLater();};
        connect(source,&QGeoPositionInfoSource::errorOccurred,this,[failed](QGeoPositionInfoSource::Error){failed();});
        source->requestUpdate(20000);
    };
    addButton(trm("gps"),[this,locate]{
        QLocationPermission permission;permission.setAccuracy(QLocationPermission::Precise);
        if(qApp->checkPermission(permission)==Qt::PermissionStatus::Undetermined){
            qApp->requestPermission(permission,this,[this,locate](const QPermission& result){if(result.status()==Qt::PermissionStatus::Granted)locate();else if(currentPage=="location")addText(trm("gpsError"));});return;
        }
        if(qApp->checkPermission(permission)==Qt::PermissionStatus::Granted)locate();else addText(trm("gpsError"));
    });
    addText(trm("latitude"));body->addWidget(lat);
    addText(trm("longitude"));body->addWidget(lon);
    addText(trm("altitude"));body->addWidget(altitude);
    addText(trm("timezone"));body->addWidget(zone);
    addButton(trm("save"),[this,lat,lon,altitude,zone,core,current]()mutable{
        auto loc=current;loc.planetName="Earth";loc.name=QString("Touch %1 %2").arg(lat->value(),0,'f',5).arg(lon->value(),0,'f',5);
        loc.region.clear();loc.role='X';loc.isUserLocation=true;loc.setLatitude(lat->value());loc.setLongitude(lon->value());loc.altitude=altitude->value();loc.ianaTimeZone=zone->currentData().toString();
        auto& manager=StelApp::getInstance().getLocationMgr();
        if(manager.canDeleteUserLocation(loc.getID()))manager.deleteUserLocation(loc.getID());
        if(!manager.saveUserLocation(loc)){addText(trm("saveError"));return;}
        core->setUseCustomTimeZone(false);core->moveObserverTo(loc,0);core->setCurrentTimeZone(loc.ianaTimeZone);core->setDefaultLocationID(loc.getID());
        auto conf=StelApp::getInstance().getSettings();conf->remove("localization/time_zone");conf->sync();panel->hide();QGuiApplication::inputMethod()->hide();
    });
    addButton(trm("advanced"),[this]{action("actionShow_Location_Window_Global");});
}
void MobileShell::lighting()
{
    auto conf=StelApp::getInstance().getSettings();
    const bool night=StelApp::getInstance().getVisionModeNight();
    const int value=qBound(5,conf->value("mobile/nightBrightness",40).toInt(),100);
    qApp->setProperty("stellarNightBrightness",value/100.0);
    conf->setValue("viewing/flag_night",night);
#ifdef Q_OS_ANDROID
    androidContext().callMethod<void>("setNightLighting","(ZIZ)V",jboolean(night),jint(value),jboolean(conf->value("mobile/keepAwake",true).toBool()));
#endif
}
void MobileShell::observing()
{
    page("observing");auto conf=StelApp::getInstance().getSettings();
    addButton(trm("night"),[]{auto& app=StelApp::getInstance();app.setVisionModeNight(!app.getVisionModeNight());});
    addText(trm("nightBrightness"));auto brightness=new QSlider(Qt::Horizontal);brightness->setRange(5,100);brightness->setValue(conf->value("mobile/nightBrightness",40).toInt());brightness->setAccessibleName(trm("nightBrightness"));brightness->setMinimumHeight(48);body->addWidget(brightness);
    connect(brightness,&QSlider::valueChanged,this,[this,conf](int value){conf->setValue("mobile/nightBrightness",value);lighting();});connect(brightness,&QSlider::sliderReleased,conf,&QSettings::sync);
    auto awake=new QCheckBox(trm("keepAwake"));awake->setChecked(conf->value("mobile/keepAwake",true).toBool());awake->setMinimumHeight(48);body->addWidget(awake);connect(awake,&QCheckBox::toggled,this,[this,conf](bool value){conf->setValue("mobile/keepAwake",value);lighting();});
    auto rate=[conf](int minimum,int maximum){auto& view=StelMainView::getInstance();view.setMinFps(minimum);view.setMaxFps(maximum);conf->setValue("video/minimum_fps",minimum);conf->setValue("video/maximum_fps",maximum);conf->sync();};
    addText(trm("performance"));addButton(trm("smooth"),[rate]{rate(2,60);});addButton(trm("battery"),[rate]{rate(1,30);});
}
void MobileShell::tools()
{
    page("tools");
    addButton(trm("plugins"),[this]{plugins();});
    auto filter=new QLineEdit;filter->setPlaceholderText(trm("filter"));filter->setAccessibleName(trm("filter"));body->addWidget(filter);
    auto list=new QListWidget;list->setUniformItemSizes(true);list->setMinimumHeight(300);list->setAccessibleName(trm("tools"));
    list->setStyleSheet("QListWidget::item{min-height:46px;padding:5px;border-bottom:1px solid #34445d;}");
    QScroller::grabGesture(list->viewport(),QScroller::TouchGesture);body->addWidget(list);
    auto manager=StelApp::getInstance().getStelActionManager();
    QHash<QString,QListWidgetItem*> items;
    for(auto a:manager->getActionList()) {
        auto item=new QListWidgetItem(a->getText(),list);item->setData(Qt::UserRole,a->getId());
        if(a->isCheckable())item->setCheckState(a->isChecked()?Qt::Checked:Qt::Unchecked);
        items.insert(a->getId(),item);
    }
    connect(filter,&QLineEdit::textChanged,list,[list](const QString& value){for(int i=0;i<list->count();++i){auto item=list->item(i);item->setHidden(!item->text().contains(value,Qt::CaseInsensitive));}});
    connect(manager,&StelActionMgr::actionToggled,list,[items](const QString& id,bool value){if(auto item=items.value(id,nullptr))item->setCheckState(value?Qt::Checked:Qt::Unchecked);});
    connect(list,&QListWidget::itemClicked,this,[this,manager](QListWidgetItem* item){if(auto a=manager->findAction(item->data(Qt::UserRole).toString())){panel->hide();a->trigger();}});
}
bool MobileShell::loadPlugin(const QString& id)
{
    auto& manager=StelApp::getInstance().getModuleMgr();
    if(manager.isPluginLoaded(id))return true;
    auto& view=StelMainView::getInstance();view.glContextMakeCurrent();
    bool success=false;
    try {
        if(auto module=manager.loadPlugin(id)) {
            manager.registerModule(module,true);manager.loadExtensions(id);module->init();success=true;
        }
    } catch(const std::exception& error) {qWarning()<<"Plugin could not initialize"<<id<<error.what();}
    view.glContextDoneCurrent();
    return success;
}
void MobileShell::plugins()
{
    page("plugins");addText(trm("pluginsHint"));
    auto filter=new QLineEdit;filter->setPlaceholderText(trm("filter"));filter->setAccessibleName(trm("filter"));body->addWidget(filter);
    auto list=new QListWidget;list->setUniformItemSizes(true);list->setMinimumHeight(300);list->setAccessibleName(trm("plugins"));list->setStyleSheet("QListWidget::item{min-height:46px;padding:5px;}");body->addWidget(list);
    QScroller::grabGesture(list->viewport(),QScroller::TouchGesture);
    for(const auto& plugin:StelApp::getInstance().getModuleMgr().getPluginsList()) {
        auto item=new QListWidgetItem((plugin.loaded?QString("✓  "):QString("+  "))+q_(plugin.info.displayedName),list);item->setData(Qt::UserRole,plugin.info.id);
    }
    connect(filter,&QLineEdit::textChanged,list,[list](const QString& value){for(int i=0;i<list->count();++i)list->item(i)->setHidden(!list->item(i)->text().contains(value,Qt::CaseInsensitive));});
    connect(list,&QListWidget::itemClicked,this,[this](QListWidgetItem* item){
        const auto id=item->data(Qt::UserRole).toString();addText(trm("loading"));
        QTimer::singleShot(100,this,[this,id]{
            if(!loadPlugin(id)){if(currentPage=="plugins")addText(trm("pluginError"));return;}
            if(panel)panel->hide();
            auto module=StelApp::getInstance().getModuleMgr().getModule(id,true);
            if(!module||!module->configureGui(true))tools();
        });
    });
}
void MobileShell::updates()
{
    page("update");
    // [20261126 by jsk] 조회 중과 최종 결과를 같은 위치에 표시하고 닫힌 화면의 응답을 무시함.
    const QPointer<QGraphicsProxyWidget> updatePage = panel;
    auto status = new QLabel(trm("checking"));
    status->setWordWrap(true);
    status->setTextFormat(Qt::PlainText);
    body->addWidget(status);
    const QPointer<QLabel> result = status;
    QUrl metadata("https://raw.githubusercontent.com/by-jsk/app-downloads/main/updates/stellar-touch.json");
#ifdef STELLAR_CI_FIXTURE
    if(androidContext().callMethod<jboolean>("isUpgradeTest"))metadata=QUrl("http://10.0.2.2:8765/stellar-touch.json");
#endif
    auto network=new QNetworkAccessManager(this);QNetworkRequest request(metadata);request.setTransferTimeout(20000);
    auto reply=network->get(request);
    connect(reply,&QNetworkReply::finished,this,[this,reply,network,result,updatePage]{auto data=reply->readAll();const auto error=reply->error();reply->deleteLater();network->deleteLater();
        if (!result || !updatePage || updatePage != panel || !updatePage->isVisible()) return;
        if(error!=QNetworkReply::NoError){result->setText(trm("updateError"));return;}auto info=QJsonDocument::fromJson(data).object();const int code=info.value("versionCode").toInt();const auto ver=info.value("versionName").toString();const auto apk=info.value("apk").toString();
        int installed=STELLAR_VERSION_CODE;
#ifdef Q_OS_ANDROID
        installed=androidContext().callMethod<jint>("installedVersionCode");
#endif
        if(code<=installed){result->setText(trm("upToDate"));return;}
        const auto expected=QString("https://github.com/by-jsk/app-downloads/releases/download/stellar-touch-v%1/StellarTouch-v%1.apk").arg(ver);
        bool fixture=false;
#ifdef STELLAR_CI_FIXTURE
        fixture=androidContext().callMethod<jboolean>("isUpgradeTest")&&apk=="http://10.0.2.2:8765/StellarTouch-v0.1.0.apk";
#endif
        if(!fixture&&(!QRegularExpression("^[0-9]+\\.[0-9]+\\.[0-9]+$").match(ver).hasMatch()||apk!=expected)){result->setText(trm("updateError"));return;}
        const auto notes=info.value("notes");const auto text=notes.isObject()?notes.toObject().value(language).toString(notes.toObject().value("en").toString()):notes.toString();result->setText(ver+"\n"+text);
        [[maybe_unused]] auto installButton = addButton(trm("installUpdate"),[this,apk,code]{
#ifdef Q_OS_ANDROID
            auto context=androidContext();
            context.callMethod<void>("downloadUpdate","(Ljava/lang/String;ILjava/lang/String;)V",QJniObject::fromString(apk).object<jstring>(),jint(code),QJniObject::fromString(QString::fromUtf8(QJsonDocument(strings.value(language).toObject()).toJson(QJsonDocument::Compact))).object<jstring>());
#else
            QDesktopServices::openUrl(QUrl(apk));
#endif
        });
#ifdef STELLAR_CI_FIXTURE
        if(fixture)QTimer::singleShot(500,this,[this,updatePage,button=QPointer<QPushButton>(installButton)]{
            if (button && updatePage == panel && updatePage->isVisible()) {
                reportUpdateButton("STELLAR_UPDATE_OFFERED", updatePage, button);
            }
        });
#endif
    });
}

void MobileShell::smokeTest()
{
    QJsonObject report;
    bool passed=true;
    auto check=[&](const QString& name,bool value){report.insert(name,value);passed=passed&&value;};
    auto conf=StelApp::getInstance().getSettings();
    report.insert("persisted_language_at_launch",conf->value("mobile/language").toString());
    report.insert("persisted_region_at_launch",conf->value("mobile/region").toString());
    auto objects=&StelApp::getInstance().getStelObjectMgr();
    const auto seoul=StelApp::getInstance().getLocationMgr().locationForString("Seoul, Eastern Asia");
    check("offline_city_catalog_available",seoul.isValid()&&qAbs(seoul.getLatitude()-37.566)<0.001&&qAbs(seoul.getLongitude()-126.9784)<0.001);
    for(const auto& name:QStringList{"Sun","Moon","Mars","Sirius","M31"}) {
        auto object=objects->searchByName(name);
        bool valid=bool(object);
        if(object){const auto pos=object->getJ2000EquatorialPos(StelApp::getInstance().getCore());valid=std::isfinite(pos[0])&&std::isfinite(pos[1])&&std::isfinite(pos[2])&&pos.norm()>0;}
        check("catalog_"+name,valid);
    }
    for(const auto& lang:QStringList{"ko","en","ja","zh","es","ru"}) {
        conf->setValue("mobile/language",lang);applyLanguage();
        check("language_"+lang,language==lang && !trm("guide").isEmpty() && trm("settings")!="settings");
        settings();auto buttons=content->findChildren<QPushButton*>();
        check("settings_order_"+lang,buttons.size()>=4&&buttons[0]->text().contains(trm("help"))&&buttons[1]->text().contains(trm("about"))&&buttons[2]->text().contains(trm("languages"))&&buttons[3]->text().contains(trm("update")));
    }
    conf->setValue("mobile/language","unsupported");applyLanguage();check("unsupported_language_falls_back_to_english",language=="en");
    conf->setValue("mobile/language","ko");conf->setValue("mobile/region","JP");applyLanguage();conf->sync();
    const auto saved = readMobileSettings(conf->fileName());
    check("independent_persisted_language_region",saved.value("mobile/language")=="ko"&&saved.value("mobile/region")=="JP");
    // [20261126 by jsk] 설치 시 마이그레이션한 별자리 선 색이 엔진과 설정 양쪽에서 적용됐는지 확인함.
    const auto constellationMgr = GETSTELMODULE(ConstellationMgr);
    const auto lineColor = constellationMgr->getLinesColor();
    check("constellation_lines_visible_by_default", constellationMgr->getFlagLines());
    check("constellation_line_palette_applied", lineColor[0]>0.5f && lineColor[1]>0.75f && lineColor[2]>0.95f
          && saved.value("color/const_lines_color").toString()==constellationLines);
    report.insert("constellation_line_rgb", QJsonArray{qRound(lineColor[0]*100)/100.0,
                  qRound(lineColor[1]*100)/100.0,qRound(lineColor[2]*100)/100.0});
    auto toggle=StelApp::getInstance().getStelActionManager()->findAction("actionShow_Constellation_Lines");
    bool toggled=false;if(toggle&&toggle->isCheckable()){const auto before=toggle->isChecked();toggle->trigger();toggled=toggle->isChecked()!=before;toggle->setChecked(before);}check("native_action_toggles_engine",toggled);
    const auto oldJD=StelApp::getInstance().getCore()->getJD();StelApp::getInstance().getCore()->setJD(2451545.0);
    check("time_sets_j2000",qAbs(StelApp::getInstance().getCore()->getJD()-2451545.0)<1e-8);
    time();auto date=content->findChild<QDateTimeEdit*>();
    check("time_editor_uses_observer_zone",date&&date->dateTime().offsetFromUtc()==qRound(StelApp::getInstance().getCore()->getUTCOffset(2451545.0)*3600));
    check("time_editor_preserves_utc",date&&qAbs(date->dateTime().toMSecsSinceEpoch()/86400000.0+2440587.5-2451545.0)<1e-8);
    StelApp::getInstance().getCore()->setJD(oldJD);
    check("all_action_catalog_available",StelApp::getInstance().getStelActionManager()->getActionList().size()>50);
    check("all_compiled_plugins_listed",StelApp::getInstance().getModuleMgr().getPluginsList().size()>=29);
    check("plugin_loads_on_demand",loadPlugin("AngleMeasure")&&StelApp::getInstance().getStelActionManager()->findAction("actionShow_Angle_Measure"));
    auto menuButton = static_cast<QToolButton*>(menuSwitch->widget());
    menuButton->click();
    check("sky_only_mode", !bar->isVisible() && !bottomBar->isVisible() && menuSwitch->isVisible());
    menuButton->click();
    check("restore_menus", bar->isVisible() && bottomBar->isVisible());
    if (objects->findAndSelect("Sirius")) {
        refreshInfo();
        static_cast<QToolButton*>(infoClose->widget())->click();
        check("dismiss_info_keeps_selection", !sky->infoPanel->isVisible() && !objects->getSelectedObject().isEmpty());
        objects->unSelect();
    }
    const bool nightBefore = nightButton->isChecked();
    nightButton->click();
    check("night_button_toggles", nightButton->isChecked()!=nightBefore);
    nightButton->click();
    check("night_button_round_trip", nightButton->isChecked()==nightBefore);
    StelApp::getInstance().setVisionModeNight(true);lighting();
    check("night_mode_saved",conf->value("viewing/flag_night").toBool());
    check("red_brightness_controlled",qApp->property("stellarNightBrightness").toDouble()>0&&qApp->property("stellarNightBrightness").toDouble()<=1);
    settings();
    report.insert("passed",passed);report.insert("versionCode",STELLAR_VERSION_CODE);report.insert("actions",StelApp::getInstance().getStelActionManager()->getActionList().size());
    report.insert("emulator_observed_fps",double(StelApp::getInstance().getFps()));
    qInfo().noquote()<<"STELLAR_SMOKE_DONE "<<QJsonDocument(report).toJson(QJsonDocument::Compact);
}
