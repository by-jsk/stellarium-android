// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 by-jsk. Independent mobile interface for Stellarium.
#include "MobileShell.hpp"
#include "MobileVersion.hpp"
#include "StelMainView.hpp"
#include "StelApp.hpp"
#include "StelCore.hpp"
#include "StelLocaleMgr.hpp"
#include "StelActionMgr.hpp"
#include "StelObjectMgr.hpp"
#include "StelMovementMgr.hpp"
#include "StelLocation.hpp"
#include "StelLocationMgr.hpp"
#include <QtWidgets>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QGeoPositionInfoSource>
#include <QGeoPositionInfo>
#include <QStandardPaths>
#ifdef Q_OS_ANDROID
#include <QJniObject>
#include <QCoreApplication>
#endif

void MobileShell::prepare()
{
    QCoreApplication::setApplicationName("StellarTouch");
    QCoreApplication::setOrganizationName("by-jsk");
    const auto config = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation) + "/config";
    QDir().mkpath(config);
    qputenv("STEL_USERDIR", config.toUtf8());
}

MobileShell::MobileShell(QGraphicsWidget* parent) : QObject(parent), root(parent)
{
    QFile file("assets:/mobile-i18n.json");
    if (file.open(QIODevice::ReadOnly)) strings = QJsonDocument::fromJson(file.readAll()).object();
    applyLanguage();
    toolbar();
    StelMainView::getInstance().installEventFilter(this);
    connect(&StelApp::getInstance(), &StelApp::languageChanged, this, [this] { toolbar(); });
    layout();
    qInfo() << "STELLAR_TOUCH_READY";
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
    if (bar) delete bar;
    auto w = new QWidget;
    w->setStyleSheet("QWidget{background:#0c1423;color:#edf3ff;font-size:13px;} QToolButton{border:1px solid #34445d;border-radius:10px;padding:4px;min-width:40px;min-height:38px;} QToolButton:pressed{background:#29466c;}");
    auto box = new QVBoxLayout(w); box->setContentsMargins(6,4,6,4); box->setSpacing(4);
    auto top = new QHBoxLayout;
    auto name = new QLabel(trm("title")); name->setMinimumWidth(0); top->addWidget(name,1);
    auto icon = [this,top](const QString& symbol, const char* key, std::function<void()> cb) {
        auto b = new QToolButton; b->setText(symbol); b->setAccessibleName(trm(key)); b->setToolTip(trm(key));
        connect(b,&QToolButton::clicked,this,cb); top->addWidget(b);
    };
    icon("?","help",[this]{help();}); icon("ⓘ","about",[this]{about();}); icon("⚙","settings",[this]{settings();});
    box->addLayout(top);
    auto bottom = new QHBoxLayout;
    auto item = [this,bottom](const char* key, std::function<void()> cb) {
        auto b = new QToolButton; b->setText(trm(key)); b->setAccessibleName(trm(key));
        b->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Preferred); connect(b,&QToolButton::clicked,this,cb); bottom->addWidget(b,1);
    };
    item("search",[this]{search();}); item("time",[this]{time();}); item("location",[this]{location();}); item("tools",[this]{tools();});
    box->addLayout(bottom);
    bar = new QGraphicsProxyWidget(root); bar->setWidget(w); bar->setZValue(250); layout();
}

void MobileShell::layout()
{
    const auto size = StelMainView::getInstance().size();
    if(bar) { bar->setPos(4,4); bar->resize(qMax(240,size.width()-8),104); }
    if(panel) { panel->setPos(6,116); panel->resize(qMax(220,size.width()-12),qMax(120,size.height()-124)); }
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
    dialog->resize(qMax(240,s.width()-16),qMax(120,s.height()-136));
    proxy->setPos(8,120); proxy->setZValue(260);
}

void MobileShell::page(const char* title)
{
    currentPage=QString::fromUtf8(title);
    if(panel) { delete panel; panel=nullptr; }
    auto frame=new QWidget;
    frame->setStyleSheet("QWidget{background:#111c2c;color:#eff5ff;font-size:15px;} QPushButton,QToolButton,QComboBox,QLineEdit,QDateTimeEdit,QDoubleSpinBox{min-height:44px;border:1px solid #3c526b;border-radius:8px;padding:4px;background:#182b42;color:#eff5ff;} QPushButton:checked{background:#375f86;} QLabel{background:transparent;} QScrollArea{border:0;}");
    auto outer=new QVBoxLayout(frame);
    auto header=new QHBoxLayout;
    auto heading=new QLabel(trm(title)); heading->setStyleSheet("font-size:19px;font-weight:bold"); header->addWidget(heading,1);
    auto close=new QToolButton; close->setText("×"); close->setAccessibleName(trm("close")); connect(close,&QToolButton::clicked,this,[this]{panel->hide(); StelMainView::getInstance().focusSky();}); header->addWidget(close);
    outer->addLayout(header);
    auto scroll=new QScrollArea; scroll->setWidgetResizable(true);
    content=new QWidget; body=new QVBoxLayout(content); body->setAlignment(Qt::AlignTop); body->setSpacing(10);
    scroll->setWidget(content); QScroller::grabGesture(scroll->viewport(),QScroller::TouchGesture); outer->addWidget(scroll);
    panel=new QGraphicsProxyWidget(root); panel->setWidget(frame); panel->setZValue(255); layout();
}
void MobileShell::addButton(const QString& label,const std::function<void()>& cb) {auto b=new QPushButton(label); b->setAccessibleName(label); connect(b,&QPushButton::clicked,this,cb); body->addWidget(b);}
void MobileShell::addText(const QString& text) {auto l=new QLabel(text); l->setWordWrap(true); l->setTextFormat(Qt::PlainText); l->setTextInteractionFlags(Qt::TextSelectableByMouse); body->addWidget(l);}
void MobileShell::action(const QString& id) {if(auto a=StelApp::getInstance().getStelActionManager()->findAction(id)) {if(panel)panel->hide(); a->trigger();}}
void MobileShell::settings() {page("settings"); addButton("?  "+trm("help"),[this]{help();}); addButton("ⓘ  "+trm("about"),[this]{about();}); addButton("文  "+trm("languages"),[this]{languages();}); addButton("↻  "+trm("update"),[this]{updates();});}
void MobileShell::help() {page("help"); addText(trm("guide"));}
void MobileShell::about() {page("about"); addText(trm("description")); addText(trm("license")); addButton(trm("source"),[]{QDesktopServices::openUrl(QUrl("https://github.com/by-jsk/stellarium-android"));}); addButton(trm("desktopSettings"),[this]{action("actionShow_Configuration_Window_Global");});}
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
    for(auto i=regions.cbegin();i!=regions.cend();++i)region->addItem(i.key()+" · "+i.value(),i.key());
    region->setCurrentIndex(qMax(0,region->findData(conf->value("mobile/region","system")))); region->setAccessibleName(trm("region")); body->addWidget(region);
    addButton(trm("save"),[this,lang,region,conf]{conf->setValue("mobile/language",lang->currentData());conf->setValue("mobile/region",region->currentData());applyLanguage();languages();});
    addButton(trm("resetDefaults"),[this,conf]{conf->remove("mobile/language");conf->remove("mobile/region");applyLanguage();languages();});
}
void MobileShell::search()
{
    page("search"); auto input=new QLineEdit; input->setPlaceholderText(trm("searchHint")); input->setAccessibleName(trm("search")); body->addWidget(input);
    auto status=new QLabel; status->setWordWrap(true); body->addWidget(status);
    auto find=[this,input,status]{auto mgr=StelApp::getInstance().getStelObjectMgr();const auto query=input->text().trimmed(); if(query.isEmpty())return;
        if(mgr->findAndSelectI18n(query)||mgr->findAndSelect(query)){auto selected=mgr->getSelectedObject();if(!selected.isEmpty()){auto movement=StelApp::getInstance().getCore()->getMovementMgr();movement->moveToObject(selected.first());movement->setFlagTracking(true);}panel->hide();}
        else status->setText(trm("notFound"));};
    addButton(trm("search"),find); connect(input,&QLineEdit::returnPressed,this,find);
    addButton(trm("advanced"),[this]{action("actionShow_Search_Window_Global");});
}
void MobileShell::time()
{
    page("time"); auto core=StelApp::getInstance().getCore();
    auto input=new QDateTimeEdit(QDateTime::fromMSecsSinceEpoch(qint64((core->getJD()-2440587.5)*86400000.0)).toLocalTime()); input->setDisplayFormat("yyyy-MM-dd HH:mm:ss"); input->setLocale(QLocale(qApp->property("stellarRegionLocale").toString())); input->setAccessibleName(trm("time")); body->addWidget(input);
    addButton(trm("applyTime"),[this,input,core]{core->setJD(input->dateTime().toUTC().toMSecsSinceEpoch()/86400000.0+2440587.5);panel->hide();});
    addButton(trm("now"),[this,core]{core->setJD(QDateTime::currentMSecsSinceEpoch()/86400000.0+2440587.5);core->setTimeRate(1.0/86400.0);panel->hide();});
    addButton(trm("pause"),[core]{core->setTimeRate(0);}); addButton("1×",[core]{core->setTimeRate(1.0/86400.0);}); addButton("100×",[core]{core->setTimeRate(100.0/86400.0);}); addButton("−100×",[core]{core->setTimeRate(-100.0/86400.0);});
    addButton(trm("advanced"),[this]{action("actionShow_DateTime_Window_Global");});
}
void MobileShell::location()
{
    page("location"); auto core=StelApp::getInstance().getCore(); auto loc=core->getCurrentLocation();
    addText(trm("latitude")); auto lat=new QDoubleSpinBox;lat->setRange(-90,90);lat->setDecimals(5);lat->setValue(loc.getLatitude());lat->setAccessibleName(trm("latitude"));body->addWidget(lat);
    addText(trm("longitude")); auto lon=new QDoubleSpinBox;lon->setRange(-180,180);lon->setDecimals(5);lon->setValue(loc.getLongitude());lon->setAccessibleName(trm("longitude"));body->addWidget(lon);
    addButton(trm("save"),[this,lat,lon,core,loc]()mutable{loc.planetName="Earth";loc.name="Stellar Touch";loc.role='X';loc.isUserLocation=true;loc.setLatitude(lat->value());loc.setLongitude(lon->value());auto& manager=StelApp::getInstance().getLocationMgr();manager.saveUserLocation(loc);core->moveObserverTo(loc,0);core->setDefaultLocationID(loc.getID());panel->hide();});
    addButton(trm("gps"),[this,lat,lon]{auto source=QGeoPositionInfoSource::createDefaultSource(this);if(!source){addText(trm("gpsError"));return;}
        QPointer<QDoubleSpinBox> latitude=lat,longitude=lon;
        connect(source,&QGeoPositionInfoSource::positionUpdated,this,[source,latitude,longitude](const QGeoPositionInfo& pos){if(latitude&&longitude){latitude->setValue(pos.coordinate().latitude());longitude->setValue(pos.coordinate().longitude());}source->deleteLater();});
        connect(source,&QGeoPositionInfoSource::errorOccurred,this,[this,source](QGeoPositionInfoSource::Error){if(currentPage=="location")addText(trm("gpsError"));source->deleteLater();});source->requestUpdate(20000);});
    addButton(trm("advanced"),[this]{action("actionShow_Location_Window_Global");});
}
void MobileShell::tools()
{
    page("tools"); auto filter=new QLineEdit;filter->setPlaceholderText(trm("filter"));filter->setAccessibleName(trm("filter"));body->addWidget(filter);
    const auto actions=StelApp::getInstance().getStelActionManager()->getActionList();
    for(auto a:actions){auto b=new QPushButton(a->getText());b->setCheckable(a->isCheckable());if(a->isCheckable()){b->setChecked(a->isChecked());connect(a,&StelAction::toggled,b,&QPushButton::setChecked);}b->setAccessibleName(a->getText());body->addWidget(b);
        connect(b,&QPushButton::clicked,this,[this,a]{panel->hide();a->trigger();});connect(filter,&QLineEdit::textChanged,b,[b](const QString& value){b->setVisible(b->text().contains(value,Qt::CaseInsensitive));});}
}
void MobileShell::updates()
{
    page("update"); addText(trm("checking"));
    auto status=new QLabel; status->setWordWrap(true);body->addWidget(status);QPointer<QLabel> result=status;
    auto network=new QNetworkAccessManager(this);QNetworkRequest request(QUrl("https://raw.githubusercontent.com/by-jsk/app-downloads/main/updates/stellar-touch.json"));request.setTransferTimeout(20000);
    auto reply=network->get(request);
    connect(reply,&QNetworkReply::finished,this,[this,reply,network,result]{auto data=reply->readAll();const auto error=reply->error();reply->deleteLater();network->deleteLater();if(!result)return;
        if(error!=QNetworkReply::NoError){result->setText(trm("updateError"));return;}auto info=QJsonDocument::fromJson(data).object();const int code=info.value("versionCode").toInt();const auto ver=info.value("versionName").toString();const auto apk=info.value("apk").toString();
        if(code<=STELLAR_VERSION_CODE){result->setText(trm("upToDate"));return;}
        const auto expected=QString("https://github.com/by-jsk/app-downloads/releases/download/stellar-touch-v%1/StellarTouch-v%1.apk").arg(ver);
        if(!QRegularExpression("^[0-9]+\\.[0-9]+\\.[0-9]+$").match(ver).hasMatch()||apk!=expected){result->setText(trm("updateError"));return;}
        const auto notes=info.value("notes");const auto text=notes.isObject()?notes.toObject().value(language).toString(notes.toObject().value("en").toString()):notes.toString();result->setText(ver+"\n"+text);
        addButton(trm("installUpdate"),[this,apk,code]{
#ifdef Q_OS_ANDROID
            auto context=QNativeInterface::QAndroidApplication::context();
            context.callMethod<void>("downloadUpdate","(Ljava/lang/String;ILjava/lang/String;)V",QJniObject::fromString(apk).object<jstring>(),jint(code),QJniObject::fromString(trm("update")).object<jstring>());
#else
            QDesktopServices::openUrl(QUrl(apk));
#endif
        });
    });
}
