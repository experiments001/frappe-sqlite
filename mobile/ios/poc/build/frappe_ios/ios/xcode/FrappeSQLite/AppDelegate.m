#import "AppDelegate.h"
#import <WebKit/WebKit.h>

@interface AppDelegate ()
@end

@implementation AppDelegate

- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    self.window = [[UIWindow alloc] initWithFrame:[[UIScreen mainScreen] bounds]];

    UIViewController *rootVC = [[UIViewController alloc] init];
    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];
    WKWebView *webView = [[WKWebView alloc] initWithFrame:rootVC.view.bounds configuration:config];
    webView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [rootVC.view addSubview:webView];

    self.window.rootViewController = rootVC;
    [self.window makeKeyAndVisible];

    NSURL *url = [NSURL URLWithString:@"http://127.0.0.1:8765"];
    NSURLRequest *request = [NSURLRequest requestWithURL:url];
    [webView loadRequest:request];

    return YES;
}

@end
